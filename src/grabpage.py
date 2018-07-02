import time
import sys
import subprocess
from selenium import webdriver

sys.exit(0)

capabilities = {
        'chromeOptions': {
            'androidPackage': 'com.amazon.mShop.android.shopping',
            'androidUseRunningApp': True,
            'androidActivity': 'com.amazon.mShop.cart.web.WebCartActivity'
            }
        }

#driver.get('http://www.google.com/xhtml');
#act = 'com.amazon.mShop.cart.web.WebCartActivity'
act = 'com.amazon.identity.auth.device.AuthPortalUIActivity'
#focused_act = subprocess.check_output("adb shell dumpsys activity | findstr mFocusedActivity", shell=True)
#print(focused_act)
capabilities['chromeOptions']['androidActivity'] = act

driver = webdriver.Remote('http://localhost:9515', capabilities)
try:
    if len(sys.argv) > 1:
        filename = "%s.html" % sys.argv[1]
    else:
        filename = "page.html"

    print("grabbed %s" % driver.current_url)
    with open(filename, 'wb') as f:
        f.write(driver.page_source.encode('utf-8'))
finally:
    driver.quit()
