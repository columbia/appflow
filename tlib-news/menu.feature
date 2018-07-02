Feature: menu
    Scenario: goto home
        Given screen is menu
        When click @home
        Then screen is list

    Scenario: goto setting
        Given screen is menu
        When click @setting
        Then screen is setting

    Scenario: goto bookmark
        Given screen is menu
        When click @bookmark
        Then screen is bookmark

    Scenario: goto signin
        Given screen is menu
        And loggedin is false
        When click @signin
        Then screen is signin

    Scenario: goto search
        Given screen is menu
        When click @search
        Then screen is search

    Scenario: see category
        Given screen is menu
        Then see @cat_item

    Scenario: switch category
        Given screen is menu
        When click @cat_item
        Then screen is list

    Scenario: search from menu
        Given screen is menu
        When click @search
        And clearfocused
        And type '@search_query'
        And kbdaction
        Then screen is searchret
        And set searched to true

    Scenario: close menu
        Given screen is menu
        Then back
