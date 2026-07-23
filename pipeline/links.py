def construct_official_url(set_num: str) -> str:
    """Naively construct a LEGO.com product URL from a Rebrickable set_num.

    Not verified against a live request — that's the official-link-checking
    seam (a later ticket). Every set gets a constructed URL and status
    'unchecked'; resolving retired/dead links happens downstream.
    """
    base_set_number = set_num.split("-")[0]
    return f"https://www.lego.com/en-us/product/{base_set_number}"
