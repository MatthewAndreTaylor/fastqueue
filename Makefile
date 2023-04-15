build:
	pip install -q build
	pip install -q twine
	pip install -q wheel
	pip install -q auditwheel
	python -m build
	auditwheel repair -w dist dist/*.whl
	find dist/ -type f -name '*.whl' ! -name '*manylinux*' -delete
	twine check dist/*.whl

clean:
	rm -rf `find . -name __pycache__`
	rm -rf *.egg-info
	rm -rf build
	rm -rf dist
