# core4build

This is a helper package to install core4os framework and projects using pip,
wheel and setuptools.

Use in ``setup.py`` of core4os projects with:

    try:
        from pip._internal.cli.main import main
    except:
        from pip import main
    
    main(["install", "--quiet", git+https://github.com/plan-net/core4build.git"])
    from core4build import setup
    
    setup(
        name='my_project',
        version="0.0.1",
        packages=["my_project"],
        include_package_data=True,
        install_requires=[...]
    )
