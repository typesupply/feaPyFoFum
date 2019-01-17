from __future__ import unicode_literals

from fontTools.misc.py23 import *
import os
import sys
import traceback
import re
from fontTools.misc.py23 import basestring, StringIO, open


class FeaPyFoFumError(Exception):
    pass


# ------------
# External API
# ------------

def compileFeatures(text, font, verbose=False, compileReferencedFiles=False):
    """
    Compile the dynamic features in the given text.

    The text is the .fea to be compiled.

    The font must be a font object that supports to the RoboFab API.

    If verbose is set to True, all code blocks will be retained
    in the compiled features. If not, they will only be shown if
    they triggered a traceback.

    If compileReferencedFiles is set to True, referenced
    files will be compiled and the references will be updated.
    The locations of the referenced files are assumed to be
    relative to the directory containing the font.
    """
    if not compileReferencedFiles:
        text = _compileFeatureText(
            text,
            font,
            verbose=verbose
        )[0]
    else:
        relativePath = None
        if font.path:
            relativePath = os.path.dirname(font.path)
        text, referencedFiles = _compileFeatureText(
            text,
            font,
            relativePath=relativePath,
            verbose=verbose
        )
        for inPath, outPath in referencedFiles:
            _compileReferencedFeatureFile(
                inPath,
                outPath,
                relativePath,
                font,
                verbose=False
            )
    return text


# ------------------
# .fea File Creation
# ------------------

def _compileFeatureText(text, font, relativePath=None, verbose=False, recursionDepth=0):
    """
    Compile the completed feature text.
    If the relativePath is given files referenced
    with include statements will be processed
    """
    referencedFiles = []
    if relativePath is not None:
        # find referenced files and update them to the new paths
        # XXX the relative path stuff here is potentially problematic.
        # XXX the .fea spec is vague about how paths should be resolved.
        if recursionDepth <= 5:
            fileMapping = _getReferencedFileMapping(text)
            for referenceInPath, referencedData in fileMapping.items():
                referenceInPath = os.path.normpath(os.path.join(relativePath, referenceInPath))
                referenceOutPath = os.path.normpath(os.path.join(relativePath, referencedData["outPath"]))
                referencedFiles.append((referenceInPath, referenceOutPath))
                text = text.replace(referencedData["target"], referencedData["replacement"])
        else:
            raise FeaPyFoFumError("Maximum reference file recursion depth exceeded.")
    # compile
    text = _executeFeatureText(text, font, verbose=verbose)
    return text, referencedFiles


def _compileReferencedFeatureFile(inPath, outPath, relativePath, font, verbose=False, recursionDepth=0):
    """
    Compile the file given in inPath and write it to outPath.
    """
    if not os.path.exists(inPath):
        # XXX silently fail here?
        return
    # compile and write this file
    with open(inPath, "r") as f:
        text = f.read()
    text, referencedFiles = _compileFeatureText(
        text,
        font,
        relativePath,
        verbose=verbose,
        recursionDepth=recursionDepth
    )
    with open(outPath, "w") as f:
        f.write(text)
    # recurse through the referenced files
    for referenceInPath, referenceOutPath in referencedFiles:
        _compileReferencedFeatureFile(
            referenceInPath,
            referenceOutPath,
            relativePath,
            font,
            verbose=verbose,
            recursionDepth=recursionDepth + 1
        )


def _getReferencedFileMapping(text):
    """
    Get a mapping of referenced files in the text.
    The returned value has this form:

        {
            originalPath : {
                outPath : new path
                target : original include statement
                replacement : new include statement
            }
        }

    All paths are relative.
    """
    referencedFiles = _findReferenceFiles(text)
    mapping = {}
    for include in referencedFiles:
        includeStart = include.index("(") + 1
        includeEnd = include.index(")")
        inPath = include[includeStart:includeEnd]
        outPath, ext = os.path.splitext(inPath)
        outPath += "-c"
        outPath += ext
        mapping[inPath] = dict(
            outPath=outPath,
            target=include,
            replacement=include[:includeStart] + outPath + include[includeEnd:]
        )
    return mapping


def _findReferenceFiles(text):
    """
    Find all include statements in the text.
    """
    text = _stripComments(text)
    pattern = re.compile(
        "include\s*\("
        "[^\)]+"
        "\s*\)"
        "\s*;"
    )
    return pattern.findall(text)


def _stripComments(text):
    """
    Strip comments from the text.
    """
    stripped = [line.split("#")[0] for line in text.splitlines()]
    return "\n".join(stripped)


# --------------
# .fea Execution
# --------------

def _executeFeatureText(text, font, verbose=False):
    """
    Compile the text in a feature file by retaining
    static lines and executing dynamic lines into
    static lines.
    """
    processed = []
    codeBlock = None
    for lineNumber, line in enumerate(text.splitlines()):
        stripeddLine = line.strip()
        if stripeddLine == "# >>>":
            codeBlock = []
        elif stripeddLine == "# <<<":
            processed += _executeCodeBlock(codeBlock, font, verbose)
            codeBlock = None
        elif codeBlock is not None:
            codeBlock.append(line)
        else:
            processed.append(line)
    return "\n".join(processed)


def _executeCodeBlock(codeBlock, font, verbose):
    """
    Process the code block and return the resulting lines.
    """
    # extract the code
    code, whitespace, constantIndent = _extractCodeFromCodeBlock(codeBlock)
    # execute
    writer = FeaSyntaxWriter(whitespace=whitespace)
    namespace = dict(
        font=font,
        writer=writer
    )
    output, errors = _executeCodeInNamespace(code, namespace)
    # compile the text
    lines = []
    if verbose or errors:
        lines.append(constantIndent + "# >>>")
        for line in codeBlock:
            lines.append(line)
        lines.append(constantIndent + "# <<<")
        lines.append("")
        if errors:
            for line in errors.splitlines():
                lines.append(constantIndent + "# " + line)
            lines.append("")
    for line in output.splitlines():
        lines.append(constantIndent + line)
    return lines


def _extractCodeFromCodeBlock(codeBlock):
    """
    Extract the executable lines, whitespace type
    and constant indent from the code block.
    """
    whitespace = None
    lines = []
    for line in codeBlock:
        if not line:
            continue
        stripped = line.strip()
        if stripped != "#":
            if not stripped.startswith("# "):
                raise FeaPyFoFumError("Non-code was found in a code block: %s" % stripped)
            ws, line = line.split("# ", 1)
            if whitespace is None:
                whitespace = ws
        lines.append(line)
    if whitespace is None or whitespace == "":
        whitespace = "\t"
        constantIndent = ""
    else:
        constantIndent = whitespace
        whitespace = whitespace[0]
    lines = "\n".join(lines)
    return lines, whitespace, constantIndent


def _executeCodeInNamespace(code, namespace):
    """
    Execute the code in the given namespace.
    """
    # This was adapted from DrawBot's scriptTools.py.
    saveStdout = sys.stdout
    saveStderr = sys.stderr
    tempStdout = StringIO()
    tempStderr = StringIO()
    try:
        sys.stdout = tempStdout
        sys.stderr = tempStderr
        try:
            code = compile(code, "", "exec", 0)
        except Exception:
            traceback.print_exc(0)
        else:
            try:
                exec(code, namespace)
            except Exception:
                etype, value, tb = sys.exc_info()
                if tb.tb_next is not None:
                    tb = tb.tb_next
                traceback.print_exception(etype, value, tb)
                etype = value = tb = None
    finally:
        sys.stdout = saveStdout
        sys.stderr = saveStderr
    output = tempStdout.getvalue()
    errors = tempStderr.getvalue()
    return output, errors


# -----------
# .fea Writer
# -----------

needSpaceBefore = "feature lookup script language".split(" ")
needSpaceAfter = "feature lookup script language".split(" ")


class FeaSyntaxWriter(object):

    def __init__(self, whitespace="\t"):
        self._featureName = None
        self._whitespace = whitespace
        self._indent = 0
        self._content = []
        self._text = []
        self._identifierStack = []
        self._inScript = False
        self._inLanguage = False

    # -----
    # Write
    # -----

    def write(self):
        # determine if contextual markers
        # need to be applied to all rules
        needContextualMarkers = False
        for item in self._content:
            if "backtrack" in item:
                if item["backtrack"] is not None or item["lookahead"] is not None:
                    needContextualMarkers = True
                    break
        if needContextualMarkers:
            for item in self._content:
                if "backtrack" in item:
                    if item["backtrack"] is None:
                        item["backtrack"] = []
                    if item["lookahead"] is None:
                        item["lookahead"] = []
        # compile the text
        text = []
        for item in self._content:
            kwargs = dict(item)
            identifier = kwargs.pop("identifier")
            methodName = "_" + identifier
            method = getattr(self, methodName)
            text += method(**kwargs)
        text += self._handleFinalBreak()
        return "\n".join(text)

    # white space

    def _handleBreakBefore(self, identifier):
        text = []
        # always need break
        if identifier in needSpaceBefore:
            text.append("")
            # need two empty lines
            if self._indent == 0 and identifier in ("feature", "lookup"):
                text.append("")
        # sequence break
        elif self._identifierStack and identifier != self._identifierStack[-1]:
            text.append("")
        return text

    def _handleFinalBreak(self):
        text = []
        if not self._identifierStack:
            pass
        elif self._identifierStack[-1] in needSpaceAfter:
            text = [""]
        return text

    def _indentLevel(self):
        return self._inScript + self._inLanguage + self._indent

    def _indentText(self, text):
        indentLevel = self._indentLevel()
        indent = self._whitespace * indentLevel
        new = []
        for i in text:
            new.append(indent + i)
        del text[:]
        text += new

    # flattening

    def _flattenClass(self, members):
        if isinstance(members, basestring):
            return members
        return "[%s]" % " ".join(members)

    def _flattenSequence(self, members):
        members = [self._flattenClass(i) for i in members]
        return " ".join(members)

    # ---------
    # Appending
    # ---------

    # blank line

    def blankLine(self):
        d = dict(
            identifier="blankLine"
        )
        self._content.append(d)

    def _blankLine(self, comment):
        text = self._handleBreakBefore("blankLine")
        text.append("")
        self._identifierStack.append("blankLine")
        return text

    # comment

    def comment(self, comment):
        if not comment.startswith("# "):
            comment = "# " + comment
        d = dict(
            identifier="comment",
            comment=comment
        )
        self._content.append(d)

    def _comment(self, comment):
        text = self._handleBreakBefore("comment")
        text.append(comment)
        self._indentText(text)
        self._identifierStack.append("comment")
        return text

    # file reference

    def formatFileReference(self, path):
        return "include({path});".format(
            path=path
        )

    def fileReference(self, path):
        d = dict(
            identifier="fileReference",
            path=path
        )
        self._content.append(d)

    def _fileReference(self, path):
        text = self._handleBreakBefore("fileReference")
        text.append(self.formatFileReference(path))
        self._indentText(text)
        self._identifierStack.append("fileReference")
        return text

    # language system

    def formatLanguageSystem(self, script, language):
        return "languagesystem {script} {language};".format(
            script=script,
            language=language
        )

    def languageSystem(self, script, language):
        d = dict(
            identifier="languageSystem",
            script=script,
            language=language
        )
        self._content.append(d)

    def _languageSystem(self, script, language):
        language = language.strip()
        text = self._handleBreakBefore("languageSystem")
        text.append(self.formatLanguageSystem(script, language))
        self._indentText(text)
        self._identifierStack.append("languageSystem")
        return text

    # script

    def formatScript(self, name):
        return "script {name};".format(
            name=name
        )

    def script(self, name):
        d = dict(
            identifier="script",
            name=name
        )
        self._content.append(d)
        # shift the indents
        self._inScript = True
        self._inLanguage = False

    def _script(self, name):
        # shift the indents back
        self._inScript = False
        self._inLanguage = False
        # write
        text = self._handleBreakBefore("script")
        text.append(self.formatScript(name))
        self._indentText(text)
        # shift the following lines
        self._inScript = True
        # done
        self._identifierStack.append("script")
        return text

    # language

    def formatLanguage(self, name):
        return "language {name};".format(
            name=name
        )

    def language(self, name, includeDefault=True):
        d = dict(
            identifier="language",
            name=name,
            includeDefault=includeDefault
        )
        self._content.append(d)
        # shift the indents
        self._inLanguage = True

    def _language(self, name, includeDefault=True):
        # shift the indent back
        self._inLanguage = False
        # write
        if name is None:
            name = "dflt"
        name = name.strip()
        text = self._handleBreakBefore("language")
        text.append(self.formatLanguage(name))
        self._indentText(text)
        # shift the following lines
        self._inLanguage = True
        # done
        self._identifierStack.append("language")
        return text

    # class definitiion

    def formatClassDefinition(self, name, members):
        return "{name} = {members};".format(
            name=name,
            members=self._flattenClass(members)
        )

    def classDefinition(self, name, members):
        d = dict(
            identifier="classDefinition",
            name=name,
            members=members
        )
        self._content.append(d)

    def _classDefinition(self, name, members):
        text = self._handleBreakBefore("classDefinition")
        text.append(self.formatClassDefinition(name, members))
        self._indentText(text)
        self._identifierStack.append("classDefinition")
        return text

    # markClass definition

    def formatMarkClassDefinition(self, members, anchor, name):
        return "markClass {members} {anchor} {name};".format(
            members=self._flattenClass(members),
            anchor=self._formatAnchorDefinition(anchor),
            name=name,
        )

    def markClassDefinition(self, members, anchor, name):
        d = dict(
            identifier="markClassDefinition",
            members=members,
            anchor=anchor,
            name=name,
        )
        self._content.append(d)

    def _markClassDefinition(self, members, anchor, name):
        text = self._handleBreakBefore("markClassDefinition")
        text.append(self.formatMarkClassDefinition(members, anchor, name))
        self._indentText(text)
        self._identifierStack.append("markClassDefinition")
        return text

    def _formatAnchorDefinition(self, anchor):
        return "<anchor {x} {y}>".format(
            x=int(anchor[0]),
            y=int(anchor[1]),
        )

    # feature

    def feature(self, name):
        writer = self.__class__(whitespace=self._whitespace)
        writer._featureName = name
        writer._indent = self._indent + 1
        d = dict(
            identifier="feature",
            name=name,
            writer=writer
        )
        self._content.append(d)
        return writer

    def _feature(self, name, writer):
        text = self._handleBreakBefore("feature")
        s = ["feature %s {" % name]
        self._indentText(s)
        text.extend(s)
        text.append(writer.write())
        s = ["} %s;" % name]
        self._indentText(s)
        text.extend(s)
        self._identifierStack.append("feature")
        return text

    # lookup

    def lookup(self, name):
        writer = self.__class__(whitespace=self._whitespace)
        writer._indent = self._indentLevel() + 1
        d = dict(
            identifier="lookup",
            name=name,
            writer=writer
        )
        self._content.append(d)
        return writer

    def _lookup(self, name, writer):
        text = self._handleBreakBefore("lookup")
        # start
        s = ["lookup %s {" % name]
        self._indentText(s)
        text.extend(s)
        text.append(writer.write())
        s = ["} %s;" % name]
        self._indentText(s)
        text.extend(s)
        self._identifierStack.append("lookup")
        return text

    def lookupflag(self, flags):
        """
        flags should be a iterable with one or several items from
        ["RightToLeft", "IgnoreBaseGlyphs", "IgnoreLigatures", "IgnoreMarks", MarkAttachmentType <glyph class name>, UseMarkFilteringSet <glyph class name>]
        """
        # XXX all lookup flags need to be regestered at once for a given lookup
        # XXX maybe this could be more flexible and different flags could be added att diferent times (?)
        d = dict(
            identifier="lookupflag",
            flags=flags
        )
        self._content.append(d)

    def _lookupflag(self, flags):
        text = self._handleBreakBefore("lookupflag")
        text.append("lookupflag %s;" % " ".join(flags))
        self._indentText(text)
        self._identifierStack.append("lookupflag")
        return text

    # feature reference

    def formatFeatureReference(self, name):
        return "feature {name};".format(
            name=name
        )

    def featureReference(self, name):
        d = dict(
            identifier="featureReference",
            name=name
        )
        self._content.append(d)

    def _featureReference(self, name):
        text = self._handleBreakBefore("featureReference")
        text.append(self.formatFeatureReference(name))
        self._indentText(text)
        self._identifierStack.append("featureReference")
        return text

    # lookup reference

    def formatLookupReference(self, name):
        return "lookup {name};".format(
            name=name
        )

    def lookupReference(self, name):
        d = dict(
            identifier="lookupReference",
            name=name
        )
        self._content.append(d)

    def _lookupReference(self, name):
        text = self._handleBreakBefore("lookupReference")
        text.append(self.formatLookupReference(name))
        self._indentText(text)
        self._identifierStack.append("lookupReference")
        return text

    # substitution

    def _formatContextTarget(self, target, backtrack, lookahead):
        if isinstance(target, basestring):
            target = [target]
        needContextMarker = backtrack is not None or lookahead is not None
        fullTarget = []
        if backtrack:
            backtrack = self._flattenSequence(backtrack)
            fullTarget.append(backtrack)
        if needContextMarker:
            target = [self._flattenClass(t) + "'" for t in target]
        target = self._flattenSequence(target)
        fullTarget.append(target)
        if lookahead:
            lookahead = self._flattenSequence(lookahead)
            fullTarget.append(lookahead)
        fullTarget = " ".join(fullTarget)
        return fullTarget

    def formatSubstitution(self, target, substitution, backtrack=None, lookahead=None, choice=False):
        fullTarget = self._formatContextTarget(target, backtrack, lookahead)
        # substitution
        if isinstance(substitution, basestring):
            substitution = [substitution]
        if substitution is not None:
            if choice:
                substitution = self._flattenClass(substitution)
            else:
                substitution = self._flattenSequence(substitution)
        # rule
        if substitution is None:
            return "ignore sub {target};".format(
                target=fullTarget
            )
        else:
            keyword = "by"
            if choice:
                keyword = "from"
            return "sub {target} {keyword} {substitution};".format(
                target=fullTarget,
                keyword=keyword,
                substitution=substitution
            )

    def substitution(self, target, substitution, backtrack=None, lookahead=None, choice=False):
        if isinstance(target, basestring):
            target = [target]
        if isinstance(substitution, basestring):
            substitution = [substitution]
        d = dict(
            identifier="substitution",
            target=target,
            substitution=substitution,
            backtrack=backtrack,
            lookahead=lookahead,
            choice=choice
        )
        self._content.append(d)

    def _substitution(self, target, substitution, backtrack=None, lookahead=None, choice=False):
        text = self._handleBreakBefore("substitution")
        text.append(
            self.formatSubstitution(
                target,
                substitution,
                backtrack=backtrack,
                lookahead=lookahead,
                choice=choice
            )
        )
        self._indentText(text)
        self._identifierStack.append("substitution")
        return text

    # ignore substitution

    def formatIgnoreSubstitution(self, target, backtrack=None, lookahead=None):
        return self.formatSubstitution(
            target=target,
            substitution=None,
            backtrack=backtrack,
            lookahead=lookahead,
            choice=False
        )

    def ignoreSubstitution(self, target, backtrack=None, lookahead=None):
        self.substitution(
            target=target,
            substitution=None,
            backtrack=backtrack,
            lookahead=lookahead,
            choice=False
        )

    # position single

    def formatPositionValue(self, value):
        if isinstance(value, basestring):
            return value
        return "<%s %s %s %s>" % value

    def _formatPositionBasic(self, target, value, backtrack, lookahead, enumerate=False):
        fullTarget = self._formatContextTarget(target, backtrack, lookahead)
        if value is not None:
            value = self.formatPositionValue(value)
        if enumerate:
            return "enum pos {target} {value};".format(
                target=fullTarget,
                value=value
            )
        elif value is None:
            return "ignore pos {target};".format(
                target=fullTarget
            )
        else:
            return "pos {target} {value};".format(
                target=fullTarget,
                value=value
            )

    def formatPositionSingle(self, target, value, backtrack=None, lookahead=None):
        return self._formatPositionBasic(target, value, backtrack, lookahead)

    def positionSingle(self, target, value, backtrack=None, lookahead=None):
        if isinstance(target, basestring):
            target = [target]
        d = dict(
            identifier="positionSingle",
            target=target,
            value=value,
            backtrack=backtrack,
            lookahead=lookahead
        )
        self._content.append(d)

    def _positionSingle(self, target, value, backtrack=None, lookahead=None):
        text = self._handleBreakBefore("positionSingle")
        text.append(
            self.formatPositionSingle(
                target,
                value,
                backtrack=backtrack,
                lookahead=lookahead
            )
        )
        self._indentText(text)
        self._identifierStack.append("positionSingle")
        return text

    # ignore position single

    def formatIgnorePositionSingle(self, target, backtrack=None, lookahead=None):
        return self.formatPositionSingle(
            target=target,
            backtrack=backtrack,
            lookahead=lookahead
        )

    def ignorePositionSingle(self, target, backtrack=None, lookahead=None):
        self.positionSingle(
            target=target,
            value=None,
            backtrack=backtrack,
            lookahead=lookahead
        )

    # position pair

    def formatPositionPair(self, target, value, backtrack=None, lookahead=None, enumerate=False):
        return self._formatPositionBasic(target, value, backtrack, lookahead, enumerate)

    def positionPair(self, target, value, backtrack=None, lookahead=None, enumerate=False):
        d = dict(
            identifier="positionPair",
            target=target,
            value=value,
            backtrack=backtrack,
            lookahead=lookahead,
            enumerate=enumerate
        )
        self._content.append(d)

    def _positionPair(self, target, value, backtrack=None, lookahead=None, enumerate=False):
        text = self._handleBreakBefore("positionPair")
        text.append(
            self.formatPositionPair(
                target,
                value,
                backtrack=backtrack,
                lookahead=lookahead,
                enumerate=enumerate
            )
        )
        self._indentText(text)
        self._identifierStack.append("positionPair")
        return text

    # subtable

    # stylistic set

    def formatStylisticSetNames(self, *names):
        lines = ["featureNames {"]
        for name in names:
            text = name["text"]
            platform = name.get("platform")
            script = name.get("script")
            language = name.get("language")
            line = ["name"]
            if platform is not None:
                line.append(str(platform))
                if script is not None:
                    line.append(str(script))
                    line.append(str(language))
            line.append(u'\"%s\"' % text)
            line = self._whitespace + " ".join(line) + ";"
            lines.append(line)
        lines.append("};")
        text = "\n".join(lines)
        return text

    def stylisticSetNames(self, *names):
        d = dict(
            identifier="stylisticSetNames",
            names=names
        )
        self._content.append(d)

    def _stylisticSetNames(self, names):
        text = self._handleBreakBefore("stylisticSetNames")
        text.extend(self.formatStylisticSetNames(*names).splitlines())
        self._indentText(text)
        self._identifierStack.append("stylisticSetNames")
        return text
