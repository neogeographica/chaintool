.PHONY: readme install devinstall uninstall dist pub testpub clean distclean

readme:
	./make_readme.py

install: readme
	python3 -m pip install .

devinstall: readme
	python3 -m pip install -e .

uninstall:
	python3 -m pip uninstall chaintool -y

dist: readme
	python3 -m build

pub: dist
	twine upload dist/*

testpub: dist
	twine upload -r testpypi dist/*

clean:
	-rm -rf build
	-find . -name '*.pyc' -exec rm {} \;
	-find . -name '__pycache__' -prune -exec rm -rf {} \;
	-find . -name '*.egg-info' -prune -exec rm -rf {} \;

distclean: clean
	-rm -rf dist
