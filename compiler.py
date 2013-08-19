import py_compile, zipfile

py_compile.compile("res_mods/8.7/scripts/client/currentvehicle.py")

fZip = zipfile.ZipFile( "XVMTankRange.zip", "w" )
fZip.write("res_mods/8.7/scripts/client/currentvehicle.pyc")
fZip.close()
