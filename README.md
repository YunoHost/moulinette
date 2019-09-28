Moulinette
==========

The *moulinette* is a Python package that allows to quickly and easily
prototype interfaces for your application.

<a href="https://translate.yunohost.org/engage/yunohost/?utm_source=widget">
<img src="https://translate.yunohost.org/widgets/yunohost/-/287x66-white.png" alt="Translation status" />
</a>

Issues
------

- [Please report issues on YunoHost bugtracker](https://dev.yunohost.org/projects/yunohost/issues) (no registration needed).

Overview
--------

Initially, the moulinette was an application made for the
[YunoHost](https://yunohost.org/) project in order to regroup all its
related operations into a single program called *moulinette*. Those
operations were available from a command-line interface and a Web server
providing an API. Moreover, the usage of these operations (e.g.
required/optional arguments) was defined into a simple YAML file -
called *actionsmap*. This file was parsed in order to construct an
*ArgumentParser* object and to parse the command arguments to process
the proper operation.

During a lengthy refactoring process with the goal of unifying both interfaces,
the idea to separate the core of the YunoHost operations has emerged.
The core kept the same name *moulinette* and tries to follow the same
initial principle. An [Actions Map](#actions-map) - defining
available operations and their usage - is parsed and used to
process an operation from several unified [interfaces](#interfaces). It
also supports a configuration mechanism - which allows restricting an
operation on an interface, for example (see
[Authenticators](#authenticators)).


### Actions Map
...

### Interfaces
...

### Authenticators
...


Requirements
------------

* Python 2.7
* python-bottle (>= 0.10)
* python-gnupg (>= 0.3)
* python-ldap (>= 2.4)
* PyYAML
