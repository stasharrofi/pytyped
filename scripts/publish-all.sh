#!/bin/bash

check_vars()
{
  var_names=("$@")
  for var_name in "${var_names[@]}"; do
    [ -z "${!var_name}" ] && echo "$var_name is unset." && var_unset=true
  done
  [ -n "$var_unset" ] && exit 1
  return 0
}

check_vars PYPI_USERNAME PYPI_PASSWORD

directories="pytyped-macros pytyped-json pytyped-metrics pytyped"

for d in $directories ; do
  echo Working on package $d
  cd $d
  rm -Rf dist/*
  ../scripts/build.sh
  ../scripts/publish.sh
  cd ..
done