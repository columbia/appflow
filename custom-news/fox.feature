Feature: fox
    @override
    @bridge
    Scenario: add bookmark from ctxmenu
        Given screen is ctxmenu
        And bookmarks is false
        When click Add to Saved
        Then screen is detail
        And set bookmarks to true

