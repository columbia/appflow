Feature: search
    @function
    Scenario: search(query)
        Then click @search_input
        And clearfocused
        And type '$query'
        And kbdaction
        #kbdoff
        #enter

    @cleantest
    @searchX
    @filterX
    @detailX
    Scenario: do a search
        Given screen is search
        When call search '@search_query'
        Then screen is searchret
        And set searched to true

    Scenario: clear search query
        Given screen is search
        When click @search_input
        And type '@search_clear_query'
        And click @search_clear
        And wait 1
        Then screen is search
        And not seetext '@search_clear_query'

    Scenario: see search keyword
        Given screen is searchret
        And searched is true
        And filtered is false
        Then seetext '@search_query'

    Scenario: see search keyword in correct place
        Given screen is searchret
        And searched is true
        And filtered is false
        Then seein @search_keyword '@search_query'

    Scenario: see price
        Given screen is searchret
        And searched is true
        And filtered is false
        Then see @item_price

    Scenario: see thumbnail
        Given screen is searchret
        And searched is true
        And filtered is false
        Then see @item_image

    Scenario: see title
        Given screen is searchret
        And searched is true
        And filtered is false
        Then see @item_title

    Scenario: see rating
        Given screen is searchret
        And searched is true
        And filtered is false
        Then see @item_rating

    Scenario: see description
        Given screen is searchret
        And searched is true
        And filtered is false
        Then see @item_desc

    @detailX
    Scenario: click title
        Given screen is searchret
        And searched is true
        And filtered is false
        When click @item_title
        Then screen is detail

    Scenario: click thumbnail
        Given screen is searchret
        And searched is true
        And filtered is false
        When click @item_image
        Then screen is detail

    @cleantest
    Scenario: click item
        Given screen is searchret
        And searched is true
        And filtered is false
        When click @searchret_item
        Then screen is detail

    @filterX
    Scenario: go to filter
        Given screen is searchret
        And filtered is false
        And searched is true
        When click @filter
        Then screen is filter

    @sortX
    Scenario: go to sort
        Given screen is searchret
        And filtered is false
        And searched is true
        When click @sort
        Then screen is sort

    Scenario: search autocomplete
        Given screen is search
        When click @search_input
        And clearfocused
        And type '@search_autocomplete_query'
        And wait 1
        Then seetext '@search_autocomplete_ret'
        And screen is search

    Scenario: no search result
        Given screen is search
        When call search '@invalid_search_query'
        And seetext '@search_nothing'
        Then set searched to false
