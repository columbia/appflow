Feature: search
    @function
    Scenario: search(query)
        When click @search_input
        And clearfocused
        And type '$query'
        And kbdaction
        #kbdoff
        #enter

    Scenario: do a search
        Given screen is search
        When call search '@search_query'
        Then screen is searchret
        And set searched to true

    Scenario: clear query
        Given screen is search
        When click @search_input
        And type '@search_clear_query'
        And wait 1
        And click @search_clear
        And not seetext '@search_clear_query'

    Scenario: autocomplete
        Given screen is search
        Then click @search_input
        And clearfocused
        And type '@search_autocomplete_query'
        And wait 1
        And seetext '@search_autocomplete_ret'

    Scenario: no result
        Given screen is search
        Then call search '@invalid_search_query'
        And see @search_nothing
