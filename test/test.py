from __future__ import unicode_literals, print_function
import os
import shutil
from defcon import Font
from feaPyFoFum import compileFeatures

text = """
languagesystem DFLT dflt;
# >>>
# writer.languageSystem("latn", "dflt")
#
# writer.classDefinition("@foo", list("bar"))
#
# featureWriter = writer.feature("fea1")
# featureWriter.comment("substitution rules")
# featureWriter.substitution("a", "a.alt")
# featureWriter.substitution(["a", "b"], "a_b")
# featureWriter.substitution([["a", "b"]], [["a.alt", "b.alt"]])
# featureWriter.substitution([["a", "a.alt"], ["b", "b.alt"]], "a_b")
# featureWriter.substitution("a_b", ["a", "b"])
# featureWriter.substitution("c", "c.alt", backtrack=["a", "b"], lookahead=["d", "e"])
# featureWriter.substitution("c", "c.alt", backtrack=[["a", "a.alt"], ["b", "b.alt"]], lookahead=[["d", "d.alt"], ["e", "e.alt"]])
# featureWriter.substitution("a", ["a.alt1", "a.alt2"], choice=True)
# featureWriter.ignoreSubstitution("a")
# featureWriter.ignoreSubstitution("b", backtrack=["a"], lookahead=["c"])
#
# lookupWriter = writer.lookup("Lookup1")
# lookupWriter.substitution("a", "a.alt")
#
# featureWriter = writer.feature("fea2")
# featureWriter.featureReference("fea1")
# featureWriter.lookupReference("Lookup1")
# featureWriter.substitution(["c", "d"], ["c.alt", "d.alt"], backtrack=["a", "b"], lookahead=["e", "f"])
# featureWriter.script("latn")
# featureWriter.language("ENG")
# lookupWriter = featureWriter.lookup("Lookup2")
# lookupWriter.substitution("a", "a.alt")
#
# print(writer.write())
# <<<

include(two.fea);
""".strip()

text = """
languagesystem DFLT dflt;
languagesystem latn dflt;

# >>>
# caseWriter = writer.feature("case")
# for name in font.glyphOrder:
#     if name.endswith(".uc"):
#         caseWriter.substitution(name.split(".")[0], name)
# print(writer.write())
# <<<

include(Blah-kern.fea);
"""

text = """
languagesystem DFLT dflt;
languagesystem latn dflt;

# >>>
# ss01Writer = writer.feature("ss01")
# ss01Writer.stylisticSetNames(
#     dict(text="Blah1"),
#     dict(text="Blah2", platform=1),
#     dict(text="Blah3", platform=1, script=2, language=3)
# )
# ss01Writer.substitution("a", "a.alt")
# print(writer.write())
# <<<

include(Blah-kern.fea);
"""

font = Font()
font.features.text = text
for name in "abcdefghijklmnopqrstuvwxyz":
	font.newGlyph(name)
	font.newGlyph(name + ".alt")
	font.newGlyph(name + ".alt1")
	font.newGlyph(name + ".alt2")
font.newGlyph("at.uc")
font.newGlyph("exclamdown.uc")
font.newGlyph("questiondown.uc")
path = os.path.join(os.path.dirname(__file__), "font.ufo")
font.save(path)

try:
	font.features.text = compileFeatures(font.features.text, font, verbose=False, compileReferencedFiles=True)
	print(font.features.text)
finally:
	shutil.rmtree(path)
