.PHONY: readme install devinstall uninstall dist pub testpub lint megalint clean distclean

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

lint:
	# Eventually should restore E501,E731. W503 should stay suppressed.
	flake8 --ignore E501,E731,W503 src/chaintool

megalint:
	# Eventually should restore all of these.
	pylint -d C0301,C0114,C0115,C0116,C0103 src/chaintool

clean:
	-rm -rf build
	-find . -name '*.pyc' -exec rm {} \;
	-find . -name '__pycache__' -prune -exec rm -rf {} \;
	-find . -name '*.egg-info' -prune -exec rm -rf {} \;

distclean: clean
	-rm -rf dist
