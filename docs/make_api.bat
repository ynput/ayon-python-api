@ECHO OFF

pushd %~dp0

poetry run sphinx-apidoc -f -e -M -o .\source\ ..\ayon_api\

