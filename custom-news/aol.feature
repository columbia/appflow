Feature: aol
    @bridge
    Scenario: go to signin
        Given screen is list
        Then click menubar_settings
        And click settings_add_new_account_button

    @override
    @bridge
    Scenario: sign in [2-step]
        Given screen is signin
        When text @email '@username'
        And click Next
        And type '@password'
        And click Sign In
        And wait 2
        Then screen is not signin
        And set loggedin to true
