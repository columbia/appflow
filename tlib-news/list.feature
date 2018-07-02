Feature: list
    Scenario: see category
        Given screen is list
        Then see @cat_item

    Scenario: switch category
        Given screen is list
        When click @cat_item
        Then screen is list

    Scenario: see image
        Given screen is list
        Then see @item_image

    Scenario: see title
        Given screen is list
        Then see @item_title

    Scenario: goto menu
        Given screen is list
        When click @menu
        Then screen is menu

    Scenario: goto ctxmenu
        Given screen is list
        When click @ctxmenu
        Then screen is ctxmenu

    Scenario: click title
        Given screen is list
        When click @item_title
        Then screen is detail

    Scenario: click image
        Given screen is list
        When click @item_image
        Then screen is detail

    @searchX
    Scenario: click item
        Given screen is list
        When click @item
        Then screen is detail

    Scenario: click search
        Given screen is list
        When click @search
        Then screen is search

    Scenario: click searchbox
        Given screen is list
        When click @searchbox
        Then screen is search
