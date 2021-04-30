*** overview

XXX talk about what this is

XXX mention that it specifically has been tested with q3map2 from netradiant-custom... other versions might work differently, or not work (e.g. not support using both -samples and -filter)

*** setup

After importing the q3build file with "chaintool import q3build", you will need to use "chaintool vals" to define a default value for the following placeholder:

  q3basepath : The absolute filepath to the Quake3 directory that you want to use for test-running your results.

So for example in my own case I would use the following command after import:

  chaintool vals q3basepath="/home/joel/Mapping/Quake3"

You may also want or need to use "chaintool vals" to set new different defaults for the following placeholders:

  q3exe (currently quake3e.x64) : The name of your Quake 3 executable. Must be located inside the q3basepath directory.

  bspc (currently mbspc.x86_64) : Your bspc executable. If this isn't currently in your executable path, use an absolute path here.

  q3map2 (currently q3map2.x86_64) : Your q3map2 executable. If this isn't currently in your executable path, use an absolute path here.

  threads (currently 7) : Generally the largest number to set here would be one less than your # of CPUs.

(Keep in mind that you can set multiple default values in the same "chaintool vals" invocation.)

There are other defaults you may want to change, for the optional parameters in the various commands, but those are more a matter of taste.


*** running

The "q3build" sequence is the main sequence to run, which will compile a Quake 3 map and then launch Quake 3 with the result. This sequence has a required "map" value that must be the absolute path of the mapfile you want to compile.

An optional "dstbase" value can also be set if you want the BSP file placed in the Quake 3 maps folder to have a different basename than your source map. For example, normally if your source map is "foo.map", which results in "foo.bsp", then "foo.bsp" will be copied into your Quake 3 installation. However if you set "dstbase" to a value of "bar", then "foo.bsp" would be copied into the Quake 3 installation as "bar.bsp".

The "q3build-simple" sequence is just like the "q3build" sequence, except that it uses the "q3light-simple" command instead of the "q3light" command.

The "q3aas" command (not sequence) can also be run to generate the bot info (.aas file) for a mapfile that you have previously compiled using one of those two sequences. It has a required "map" value that must be the absolute path to the .bsp file (or to the .map file if it is in the same directory).

XXX actually need to make this into a sequence that also at least copies the .aas file into the Quake 3 installation

There are several available toggles and optional parameters for customizing the command behaviors.

XXX insert a quick rundown of those in here


*** cleanup

The items created by this import can be deleted with:

  chaintool seq del q3build q3build-simple
  chaintool cmd del q3bsp q3vis q3light q3light-simple q3set-opt-dest q3copy q3launch q3aas
