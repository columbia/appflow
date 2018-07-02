Feature: bookmark
    Scenario: see empty
        Given screen is bookmark
        And bookmarks is false
        Then see @empty

    @observe
    Scenario: observe by see empty
        Given screen is bookmark
        When see @empty
        Then set bookmarks to false

    @observe
    Scenario: observe by no empty
        Given screen is bookmark
        When not see @empty
        Then set bookmarks to true

    @observe
    Scenario: observe by no item
        Given screen is bookmark
        When not see @item
        Then set bookmarks to false

    Scenario: del bookmark [through detail]
        Given screen is bookmark
        And bookmarks is true
        When click @item
        And click @bookmark
        And back
        And wait 3
        And not see @item
        Then screen is bookmark
        And set bookmarks to false

    Scenario: del bookmark [directly]
        Given screen is bookmark
        And bookmarks is true
        When click @item_remove
        And see @empty
        Then screen is bookmark
        And set bookmarks to false

    Scenario: del bookmark [through menu]
        Given screen is bookmark
        And bookmarks is true
        When click @item_menu
        And click @item_remove
        And see @empty
        Then screen is bookmark
        And set bookmarks to false

    Scenario: click bookmark
        Given screen is bookmark
        And bookmarks is true
        When click @item
        Then screen is detail
