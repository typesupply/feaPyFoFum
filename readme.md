A compiler that will replace Python code blocks embedded in .fea with compiled .fea. This allows the .fea code to be dynamic.

**This is a work in progress. If you want to see how to use it right now, look at the main test in `test/test.py`. This documentation will be better when the code is more stable. Probably.**

# The General Idea

I don't know about you, but my glyph sets change frequently during development. The features in my fonts are based on the available glyphs. It's annoying and time consuming to keep .fea files in sync with these moving glyph sets. Then if the *Bold* doesn't have the alternate ampersand that the *Light* has...*chaos*. Dynamic features will make these problems much easier to deal with.

Furthermore, when developing extremely complex features (ie fancy swashes) I have been using Python scripts to do the actual .fea compilation for years. The code in those scripts is often 90% shorter and 90,000,000% more readable than the compiled .fea code. This workflow works really, really well until I have to start adding static features (ie a simple `locl`). Then I have to use cumbersome ways to combine the static and the automatic. This new method of embedding the Python code within the .fea allows these to be seamlessly combined. Simple `locl` AND complex `cswh` in the same file!

# Python Code Blocks

The beginning of a code block is indicated with `# >>>` and `# <<<` indicates the end of a block. Each line between these must begin with a `#` forllowed by a space. Any amount of whitespace before the `#` is allowed. The code blocks can be freely mixed within regular .fea code.

The codeblocks will have two objects availble by default:

* `font`: A font supporting the RoboFab API.
* `writer`: A simple, but powerful, .fea writer. (See below for API reference.)

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

## Writer API

(Ha ha. The reference isn't here yet. Look in the feaPyFoFum.py file for now. Sorry.)


# To Do

* Complete the writer.
	- lookupflag
	- positioning
	- use extension
	- ssXX names
	- probably other stuff
* Clean up the output from the writer.
    - http://opentypecookbook.com/style-guide.html
    - The identifier system seems to be going haywire
      and inserting unnecessary blank lines.
* Test cases.
* Add commandline tool.
* Write better documentation.
	- How to use as a module.
	- Writer API
	- More examples: .sc, complex contextual using glyph.note, quantum random