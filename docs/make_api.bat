@ECHO OFF

pushd %~dp0

sphinx-apidoc -f -e -M -o .\source\ ..\ayon_api\

