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


def yoloswag_version(*args, **kwargs):
    return "666"
