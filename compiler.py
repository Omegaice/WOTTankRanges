import py_compile, zipfile

py_compile.compile("res_mods/0.8.7/scripts/client/currentvehicle.py")

fZip = zipfile.ZipFile( "XVMTankRange.zip", "w" )
fZip.write("res_mods/0.8.7/scripts/client/currentvehicle.pyc")
fZip.close()

fZip = zipfile.ZipFile( "XVMTankRange-WithXVM.zip", "w" )
fZip.write("res_mods/0.8.7/scripts/client/currentvehicle.pyc")
fZip.write("res_mods/0.8.7/gui/flash/Minimap.swf")
fZip.write("res_mods/xvm/xvm.xc")
fZip.close()
