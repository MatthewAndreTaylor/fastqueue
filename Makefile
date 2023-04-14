build:
	python3 -m build 

clean:
	rm -rf `find . -name __pycache__`
	rm -rf *.egg-info
	rm -rf build