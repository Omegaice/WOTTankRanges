import py_compile, zipfile

py_compile.compile("res_mod/8.7/script/client/currentvehicle.py")

fZip = zipfile.ZipFile( "XVMTankRange.zip", "w" )
fZip.write("res_mod/8.7/script/client/currentvehicle.pyc")
fZip.close()
