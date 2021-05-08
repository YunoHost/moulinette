[![Build Status](https://travis-ci.org/YunoHost/moulinette.svg?branch=stretch-unstable)](https://travis-ci.org/YunoHost/moulinette)
[![GitHub license](https://img.shields.io/github/license/YunoHost/moulinette)](https://github.com/YunoHost/moulinette/blob/stretch-unstable/LICENSE)

Moulinette
==========

The *moulinette* is a Python package that allows to quickly and easily
prototype interfaces for your application.

<a href="https://translate.yunohost.org/engage/yunohost/?utm_source=widget">
<img src="https://translate.yunohost.org/widgets/yunohost/-/287x66-white.png" alt="Translation status" />
</a>

Issues
------

- [Please report issues on YunoHost bugtracker](https://github.com/YunoHost/issues).

Overview
--------

Initially, the moulinette was an application made for the
[YunoHost](https://yunohost.org/) project in order to regroup all its
related operations into a single program called *moulinette*. Those
operations were available from a command-line interface and a Web server
providing an API. Moreover, the usage of these operations (e.g.
required/optional arguments) was defined into a simple yaml file -
called *actionsmap*. This file was parsed in order to construct an
*ArgumentParser* object and to parse the command arguments to process
the proper operation.

During a long refactoring with the goal of unify both interfaces, the
idea to separate the core of the YunoHost operations has emerged.
The core kept the same name *moulinette* and try to follow the same
initial principle. An [Actions Map](#actions-map) - which defines
available operations and their usage - is parsed and it's used to
process an operation from several unified [Interfaces](#interfaces). It
also supports a configuration mechanism - which allows to restrict an
operation on an interface for example (see
[Authenticators](#authenticators)).


Dev Documentation
-----------------

https://moulinette.readthedocs.org


Testing
-------

```
$ pip install tox
$ tox
```
