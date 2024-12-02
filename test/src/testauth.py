#!/usr/bin/env python3
#
# Copyright (c) 2024 YunoHost Contributors
#
# This file is part of YunoHost (see https://yunohost.org)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#


def testauth_none():
    return "some_data_from_none"


def testauth_subcat_none():
    return "some_data_from_subcat_none"


def testauth_default():
    return "some_data_from_default"


def testauth_subcat_default():
    return "some_data_from_subcat_default"


def testauth_subcat_post():
    return "some_data_from_subcat_post"


def testauth_other_profile():
    return "some_data_from_other_profile"


def testauth_subcat_other_profile():
    return "some_data_from_subcat_other_profile"


def testauth_only_api():
    return "some_data_from_only_api"


def testauth_only_cli():
    return "some_data_from_only_cli"


def testauth_with_arg(super_arg):
    return super_arg


def testauth_with_extra_str_only(only_a_str):
    return only_a_str


def testauth_with_type_int(only_an_int):
    return only_an_int
