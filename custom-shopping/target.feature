Feature: target

    @app
    Scenario: login at checkout
        Given screen is app_target_precheckout
        And loggedin is true
        When text login_account '@username'
        And text login_password '@password'
        And click sign in
