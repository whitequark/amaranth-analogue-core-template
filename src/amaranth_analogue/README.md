This directory contains glue code that connects, on one side, to the interfaces and libraries
provided by Analogue, and on the other side, to Amaranth code following common idioms. It provides
a so-called Amaranth platform specialized for Analogue Pocket. While there is a platform provided
by Amaranth itself for the FPGA that is used in Analogue Pocket, this device has unique properties
and needs customizations not readily available as a part of a normal Amaranth build process.

You can modify the code in this directory because this is your private copy of it, but this is not
recommended; if you ever need to update this code to use features added in a new Analoge Pocket
firmware revisions, you would have to port your local changes as well. Whenever possible it is
preferred to modify the toplevel project files (in the `src/amaranth_analogue_example` folder, in
the template repository).
