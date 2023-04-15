build:
	pip install -q build
	pip install -q twine
	pip install -q wheel
	pip install -q auditwheel
	python3 -m build
	auditwheel repair -w dist dist/*.whl
	twine check dist/*.whl

clean:
	rm -rf `find . -name __pycache__`
	rm -rf *.egg-info
	rm -rf build
	rm -rf dist
