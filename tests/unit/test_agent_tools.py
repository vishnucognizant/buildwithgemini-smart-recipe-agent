# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit tests for Smart Recipe Agent tools and functions.
"""

from app.agent import (
    root_agent,
    search_public_recipes,
    get_food_product_info,
    search_recipes,
)


def test_root_agent_tools_configured() -> None:
    """Verify that root_agent has tools configured."""
    assert root_agent is not None
    assert len(root_agent.tools) > 0


def test_search_public_recipes() -> None:
    """Test searching public recipes via TheMealDB."""
    results = search_public_recipes("chicken")
    assert isinstance(results, list)


def test_get_food_product_info() -> None:
    """Test nutrition product lookup via Open Food Facts."""
    results = get_food_product_info("avocado")
    assert isinstance(results, list)


def test_search_recipes_firestore() -> None:
    """Test searching local Firestore recipes."""
    results = search_recipes("toast")
    assert isinstance(results, list)
