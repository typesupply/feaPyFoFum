This project is a compiler for the FeaPy syntax. Coincidentally, this project defines the FeaPy syntax and requirements for implementing it.

**This is a work in progress. If you want to see how to use it right now, look at the main test in `test/test.py`. This documentation will be better when the code is more stable. Probably.**

# FeaPy

The FeaPy syntax is a simple, backwards compatible addition to the syntax defined in Adobe's OpenType Feature File Specification (.fea). The additions to the syntax allow for embedding and noting Python code blocks behind comments. This Python code is executed and the results are added to the .fea file. This allows .fea to become dynamic. This is hugely useful.

## The General Idea

I don't know about you, but my glyph sets change frequently during development. The features in my fonts are based on the available glyphs. It's annoying and time consuming to keep .fea files in sync with these moving glyph sets. Then if the *Bold* doesn't have the alternate ampersand that the *Light* has...*chaos*. Dynamic features will make these problems much easier to deal with.

Furthermore, when developing extremely complex features (ie fancy swashes) I have been using Python scripts to do the actual .fea compilation for years. The code in those scripts is often 90% shorter and 90,000,000% more readable than the compiled .fea code. This workflow works really, really well until I have to start adding static features (ie a simple `locl`). Then I have to use cumbersome ways to combine the static and the automatic. This new method of embedding the Python code within the .fea allows these to be seamlessly combined. Simple `locl` AND complex `cswh` in the same file!

## Examples

```
languagesystem DFLT dflt;
languagesystem latn dflt;

# >>>
# caseWriter = writer.feature("case")
# for name in font.glyphOrder:
#     if name.endswith(".uc"):
#         caseWriter.substitution(name.split(".")[0], name)
# print writer.write()
# <<<

include(Blah-kern.fea);
```

This will compile to:

```
languagesystem DFLT dflt;
languagesystem latn dflt;



feature case {
	sub at by at.uc;
	sub exclamdown by exclamdown.uc;
	sub questiondown by questiondown.uc;
} case;


include(Blah-kern-c.fea);
```

## Syntax and Implementation Requirements

The beginning of a code block is indicated with `# >>>` and `# <<<` indicates the end of a block. Each line between these must begin with a `#` followed by a space. Any amount of whitespace before the `#` is allowed. The code blocks may be freely mixed within regular .fea code.

These code blocks are executed with Python and the resulting data written to `stdout` must be added to the .fea in place of the original code. An implementation may retain the original code and add the data written to `stdout` after the code block. If anything is written to `stderr`, it may be written into the .fea behind comment markers.

The namespace in which the code blocks are executed must have two global insertions:

* `font` A font object supporting the RoboFab API.
* `writer` A .fea writer with a standard API.


### Writer API

The `writer` object can serve two functions. One is to simply format particular inputs into the appropriate .fea syntax. The other is to act as a slightly smarter line compiler that will help make decisions about syntax in a broader scope than a single line. This may also handle pretty-formatting the code.

#### Line Compiler Mode

##### writer.blankline()

Write a blank line.

##### writer.comment(text)

Write a comment. If the text doesn't begin with a `#`, add it.

##### writer.fileReference(path)

##### writer.languageSystem(script, language)

##### writer.script(name)

##### writer.language(name, includeDefault=True)

##### writer.classDefinition(name, members)

##### writer.feature(name)

This will return another writer object specifically for writing data to the newly defined feature.

##### writer.lookup(name)

This will return another writer object specifically for writing data to the newly defined lookup.

##### writer.featureReference(name)

##### writer.lookupReference(name)

##### writer.substitution(target, substitution, backtrack=None, lookahead=None, choice=False)

If `choice` is `True` the rule will be written as a `from` rule (GSUB LookupType 3). During the concluding `write` call, all rules within the writer's scope written using a `substitution` call will be inspected to determine if contextual marking (`'`) is necessary. If one rule needs the marking, all rules will recieve it in accordance with the .fea specification.

##### writer.ignoreSubstitution(target, backtrack=None, lookahead=None)

The same contextual marking defined in the `substitution` method will be run for `ignoreSubstitution`.

##### writer.write()

Return a string containing everything stored in the writer properly formatted for .fea.


#### Formatting Mode

The `format*` functions compile a string into the proper format and return it. Nothing will be written to `stdout` or stored for later writing. That is up to the caller.

##### writer.formatFileReference(path)

##### writer.formatLanguageSystem(script, language)

##### writer.formatScript(name)

##### writer.formatLanguage(name)

##### writer.formatClassDefinition(name, members)

##### writer.formatFeatureReference(name)

##### writer.formatLookupReference(name)

##### writer.formatSubstitution(target, substitution, backtrack=None, lookahead=None, choice=False)

This will only assume that the substitution rule should contain contextual marking (`'`) if `lookahead` or `backtrack` are not None. If `choice` is `True` the rule will be written as a `from` rule (GSUB LookupType 3).

##### writer.formatIgnoreSubstitution(target, backtrack=None, lookahead=None)

This will only assume that the substitution rule should contain contextual marking (`'`) if `lookahead` or `backtrack` are not None.


# FeaPyFoFum

FeaPyFoFum is a compiler for FeaPy code. It's a little Python module that you can import and use in your build scripts. Font editors may also embed it and make it an option when generating.

To encorporate this into your build scripts, import the `compileFeatures` function and use it like this:

```python
import os
from feaPyFoFum import compileFeatures

font = CurrentFont()

# compile the dynamic features
originalFeatures = font.features.text
font.features.text = compileFeatures(
    originalFeatures,
    font,
    compileReferencedFiles=True
)

# generate the binary
path = os.path.splitext(font.path)[0] + ".otf"
font.generate(path, "otf")

# restore the original features
font.features.text = originalFeatures
```

This snippet will compile the features, put them in the font, generate an OTF-CFF and restore the original features. If any external files are referenced with `include` statements, those files will be compiled to new files (same location and file name, but a "-c" will be added to the file name) and the include statements will be redirected to the new files.

# To Do

* Complete the writer.
	- raw
	- lookupflag
	- positioning
	- use extension
	- ssXX names
	- probably other stuff
* Clean up the output from the writer.
    - http://opentypecookbook.com/style-guide.html
    - The identifier system seems to be going haywire and inserting unnecessary blank lines.
* Test cases.
* Add commandline tool.
* Write better documentation.
	- How to use as a module.
	- Writer API
	- More examples: .sc, complex contextual using glyph.note, quantum random