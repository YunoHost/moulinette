<h1 align="center">Moulinette</h1>

<div align="center">
 
![Version](https://img.shields.io/github/v/tag/yunohost/moulinette?label=version&sort=semver)
[![Tests status](https://github.com/YunoHost/moulinette/actions/workflows/tox.yml/badge.svg)](https://github.com/YunoHost/moulinette/actions/workflows/tox.yml)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/YunoHost/moulinette.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/YunoHost/moulinette/context:python)
[![GitHub license](https://img.shields.io/github/license/YunoHost/moulinette)](https://github.com/YunoHost/moulinette/blob/dev/LICENSE)

 
Moulinette is a small Python framework meant to easily create programs with unified CLI and API.

In particular, it is used as a base framework for the YunoHost project.
 
</div>

Issues
------

- [Please report issues on YunoHost bugtracker](https://github.com/YunoHost/issues).

Overview
--------

Moulinette allows to create a YAML "actionmaps" that describes what commands are available. Moulinette will automatically make these commands available through the CLI and Web API, and will be mapped to a python function. Moulinette also provide some general helpers, for example for logging, i18n, authentication, or common file system operations.

<div align="center"><img src="doc/actionsmap.png" width="700" /></div>

Translation
-----------

You can help translate Moulinette on our [translation platform](https://translate.yunohost.org/engage/yunohost/?utm_source=widget)

<div align="center"><img src="https://translate.yunohost.org/widgets/yunohost/-/moulinette/horizontal-auto.svg" alt="Translation status" /></div>

Developpers
-----------

- You can learn how to get started with developing on YunoHost by reading [this piece of documentation](https://yunohost.org/dev).
- Specific doc for moulinette: https://moulinette.readthedocs.org
- Run tests with:

```
$ pip install tox
$ tox
```
