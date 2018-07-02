Feature: poshmark

    @bridge
    Scenario: to account
        Given screen is main
        And loggedin is true
        When click userTab
        Then screen is account

    @bridge
    Scenario: click address to edit
        Given screen is address
        When click @address_item
        Then screen is addredit

    @override
    Scenario: filter by size [no confirm, select cat first]
        Given screen is filter
        And filtered is false
        When click @filter_size
        And click Select Category For Specific Sizes
        And click Bags
        And click !marked:'@filter_size_name'
        And click APPLY
        Then screen is searchret
        And set filtered to true


