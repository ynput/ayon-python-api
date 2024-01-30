@ECHO OFF

pushd %~dp0

poetry run sphinx-apidoc -f -o ../docs/source/ ../ ../tests ../*setup*