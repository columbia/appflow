Feature: detail
    Scenario: see ctxmenu
        Given screen is detail
        Then see @ctxmenu

    Scenario: goto ctxmenu
        Given screen is detail
        When click @ctxmenu
        Then screen is ctxmenu

    Scenario: see bookmark
        Given screen is detail
        Then see @bookmark

    Scenario: add bookmark [not loggedin]
        Given screen is detail
        And loggedin is false
        And bookmarks is false
        When click @bookmark
        Then set bookmarks to true

    Scenario: add bookmark [loggedin]
        Given screen is detail
        And loggedin is true
        And bookmarks is false
        When click @bookmark
        Then set bookmarks to true

    Scenario: see share
        Given screen is detail
        Then see @share

    Scenario: see title
        Given screen is detail
        Then see @title

    Scenario: see image
        Given screen is detail
        Then see @image

    Scenario: see text
        Given screen is detail
        Then see @text

    Scenario: go back
        Given screen is detail
        Then back
