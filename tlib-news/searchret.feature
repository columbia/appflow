Feature: searchret
    Scenario: see keyword
        Given screen is searchret
        And searched is true
        Then seein @keyword '@search_query'

    Scenario: see image
        Given screen is searchret
        And searched is true
        Then see @item_image

    Scenario: see title
        Given screen is searchret
        And searched is true
        Then see @item_title

        #    @screen(searchret)
        #    @searched(1)
        #    Scenario: see author
        #        see @item_author

    Scenario: see time
        Given screen is searchret
        And searched is true
        Then see @item_time

    @detailX
    Scenario: click title
        Given screen is searchret
        And searched is true
        When click @item_title
        Then screen is detail

    Scenario: click image
        Given screen is searchret
        And searched is true
        When click @item_image
        Then screen is detail

    Scenario: click item
        Given screen is searchret
        And searched is true
        When click @item
        Then screen is detail

    @sortX
    Scenario: go to sort
        Given screen is searchret
        And searched is true
        When click @sort
        Then screen is sort
