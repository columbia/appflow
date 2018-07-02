Feature: ctxmenu
    Scenario: goto setting
        Given screen is ctxmenu
        When click @setting
        Then screen is setting

    Scenario: goto signin
        Given screen is ctxmenu
        When click @signin
        Then screen is signin

    Scenario: change size
        Given screen is ctxmenu
        When click @textsize
        Then screen is textsize

