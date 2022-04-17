directories="pytyped-macros pytyped-json pytyped-metrics pytyped"
for d in $directories ; do
  echo Working on package $d
  cd $d
  rm -Rf dist/*
  ../scripts/build
  ../scripts/publish
  cd ..
done