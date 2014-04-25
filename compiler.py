import py_compile, zipfile, os, glob

WOTVersion = "0.9.0"

# Compile Source
py_compile.compile("src/currentvehicle.py")

# Build Standalone Zip
if os.path.exists("XVMTankRange.zip"):
	os.remove("XVMTankRange.zip")

fZip = zipfile.ZipFile( "XVMTankRange.zip", "w" )
fZip.write("src/currentvehicle.pyc", "res_mods/"+WOTVersion+"/scripts/client/currentvehicle.pyc")
fZip.write("data/tankrange.xc", "res_mods/xvm/tankrange.xc")
fZip.close()

# Build XVM Zip
if os.path.exists("XVMTankRange-WithXVM.zip"):
	os.remove("XVMTankRange-WithXVM.zip")

fZip = zipfile.ZipFile( "XVMTankRange-WithXVM.zip", "w" )
fZip.write("src/currentvehicle.pyc", "res_mods/"+WOTVersion+"/scripts/client/currentvehicle.pyc")
fZip.write("data/tankrange.xc", "res_mods/xvm/tankrange.xc")
for root, dirnames, filenames in os.walk('xvm'):
	for filename in filenames:
		fZip.write(os.path.join(root, filename), "res_mods/"+os.path.join(root, filename)[4:])
fZip.close()
