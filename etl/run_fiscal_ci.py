#!/usr/bin/env python3
"""Run the fiscal ETL with narrowly scoped ONP resilience for CI."""

import requests

from etl import populate_fiscal_arg as fiscal


_original_get_onp_response = fiscal.get_onp_response
_original_fetch_aif_links = fiscal.fetch_aif_links


def get_onp_response_with_pinned_fallback(url, timeout=60):
  """Use the existing pinned ONP certificate for any TLS-chain failure."""
  try:
    return _original_get_onp_response(url, timeout=timeout)
  except requests.exceptions.SSLError:
    fiscal.LOGGER.warning(
      "ONP normal TLS validation failed; retrying with the pinned certificate"
    )
    return fiscal.ONP_PINNED_SESSION.get(url, timeout=timeout)


def fetch_aif_links_allow_missing_year(year):
  """Skip an unavailable historical ONP year while keeping other HTTP errors fatal."""
  try:
    return _original_fetch_aif_links(year)
  except requests.exceptions.HTTPError as exc:
    if exc.response is not None and exc.response.status_code == 404:
      fiscal.LOGGER.warning(
        "Skipping unavailable ONP execution page for %s: %s",
        year,
        exc.response.url,
      )
      return []
    raise


fiscal.get_onp_response = get_onp_response_with_pinned_fallback
fiscal.fetch_aif_links = fetch_aif_links_allow_missing_year
fiscal.main()
