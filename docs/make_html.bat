@ECHO OFF

pushd %~dp0

sphinx-build -M html .\source .\build
