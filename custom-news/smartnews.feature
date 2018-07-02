Feature: smartnews
    @app
    Scenario: turn welcome page
        Given screen is app_smartnews_welcome
        Then scrollit curlView right

    @bridge
    Scenario: goto setting from list
        Given screen is list
        When scroll up
        And click settingButton
        Then screen is setting
