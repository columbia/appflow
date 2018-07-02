Feature: nbc
    @override
    Scenario: clear query [no click]
        Given screen is search
        Then type '@search_clear_query'
        And wait 1
        And click @search_clear
        And not seetext '@search_clear_query'

    @override
    Scenario: no result [no click]
        Given screen is search
        When clearfocused
        And type '@invalid_search_query'
        And kbdaction
        And see @search_nothing

    @override
    @bridge
    Scenario: do a search [no click]
        Given screen is search
        When clearfocused
        And type '@search_query'
        And kbdaction
        And back
        And wait 1
        And back
        Then screen is searchret
        And set searched to true

