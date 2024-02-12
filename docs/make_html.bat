@ECHO OFF

pushd %~dp0

poetry run sphinx-build -M html .\source .\build
