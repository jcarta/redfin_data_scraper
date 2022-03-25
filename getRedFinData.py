# -*- coding: utf-8 -*-
"""
Created on Fri Mar 18 20:20:19 2022

Determines whether a RedFin listing  will cash flow

@author: jcartagena
"""

from IPython import get_ipython
get_ipython().magic('clear')

# constants
term = 30 # years
rate = 0.04375 # FHA: 4.125%, Conv: 4.375% as of 3/22/22
pmi_pct = 0.0105 # FHA: 1.05% of loan amount
insurance_pct = 0.004 # 0.4% of list price
downpayment_pct = 0.05 # FHA: 3.5%, Conventional: 5% (owner occupied)
closing_costs_pct = 0.02 # 2% is typical for McGlone
expenses = 536.96 # monthly (utilities, reserves, maintenance, etc)

groveSt_rent = 3200
groveSt_piti = 2598.28

import requests
import datetime
from re import sub
import numpy as np
import pandas as pd
from decimal import Decimal
import numpy_financial as npf
from bs4 import BeautifulSoup
from selenium import webdriver

# get rent from Zillow
def getZestimate(driver, address):
    address.replace(" ", "-").replace(",","")
    rent_url = "https://www.zillow.com/rental-manager/price-my-rental/results/" + address
    driver.get(rent_url)
    rent_data = driver.page_source
    rent_soup = BeautifulSoup(rent_data,'html.parser')
    
    try:
        zestimate = rent_soup.find("h2", class_="Text-c11n-8-64-1__sc-aiai24-0 eFOYNq").text
        zestimate = int(Decimal(sub(r'[^\d.]', '', zestimate)))
    except:
        print("Property does not have a rent estimate, setting rent to zero")
        zestimate = 0
        
    return zestimate

# get timestamp
ct = str(datetime.datetime.now().strftime("%m-%d-%Y_%H%M%S"))

# set up driver parameters
chrome_options = webdriver.ChromeOptions()
chrome_options.headless = True
chrome_options.add_argument("--proxy-server='direct://'")
chrome_options.add_argument("--proxy-bypass-list=*")
chrome_options.add_argument('blink-settings=imagesEnabled=false')

driver = webdriver.Chrome("chromedriver", options=chrome_options)

# this is the saved "Automated MA House Hack" search url
# areas: middlesex, suffolk, and norfolk counties
# price range: 0-$1.25M, beds: 3+, baths: 2+, type: multifamily
# status: "active", "coming soon", no HOA fees, no new construction
# exclude 55+ communities, short sales, and land leases
search_url = "https://www.redfin.com/county/1344/MA/Norfolk-County/filter/" + \
             "property-type=multifamily,max-price=1.25M,min-beds=3," + \
             "min-baths=2,hoa=0,include=forsale+fsbo,exclude-short-sale," + \
             "exclude-age-restricted,exclude-land-lease,mr=5:1346+5:1342"

driver.get(search_url)
search_data = driver.page_source
search_soup = BeautifulSoup(search_data,'html.parser')

download_url = "https://www.redfin.com" + str(search_soup.find("a", id="download-and-save")["href"])

# postman user agent: PostmanRuntime/7.26.10
headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36(KHTML, like Gecko) Chrome/99.0.4844.82 Safari/537.36 Edg/99.0.1150.36',
  #'Authorization': 'Basic amFiaWVyY2FydGFnZW5hQGdtYWlsLmNvbTpLSXdYc0M3blphQXNidDFJVEF3Ug==',
  #'Cookie': 'RF_BID_UPDATED=1; RF_BROWSER_ID=_jrORlGfQJyzST1Hn6CAOQ; RF_MARKET=boston'
}

# request the data dump from RedFin
response = requests.get(download_url, headers=headers).content

# save data to a CSV file
with open("redfin_data.csv", 'wb') as outfile:
    outfile.write(response)

# read in RedFin URLs
df_in = pd.read_csv("redfin_data.csv", usecols=[20])

# set headers for output files
params = {
    'Term': [term],
    'Interest Rate (%)': [rate],
    'PMI (%)': [pmi_pct],
    'Insurance (%)': [insurance_pct],
    'Down Payment (%)': [downpayment_pct],
    'Closing Costs (%)': [closing_costs_pct],
    'Monthly Expenses': [expenses],
    '30GroveSt Mortgage': [groveSt_piti],
    '30GroveSt Rent': [groveSt_rent]
}  

data_out = {
    'MLS': [],
    'Address': [],
    'Town/City': [],
    'Property Type':[],
    'List Price': [],
    'RedFin Estimate': [],
    'Beds': [],
    'Baths':[],
    'SQFT': [],
    'MFH Mortgage Payment': [],
    'MFH Zestimate': [],
    'Monthly Savings': [],
    'MFH Cash Flow': [],
    'MFH Cash-on-Cash Return (%)': [],
    'Combined Cash Flow': [],
    'Cap Rate (%)': [],
    'Interested?': [],
    'URL': []
}  

df_out = pd.DataFrame(data_out)
df_param = pd.DataFrame(params)

fn_out = "output_" + ct + ".csv"
fn_param = "parameters_" + ct + ".csv"

df_out.to_csv(fn_out, mode='a', index=False, header=True)
df_param.to_csv(fn_param, mode='a', index=False, header=True)
    
for i in range(0, len(df_in)):
    
    print(str(i+1) + " of " + str(len(df_in)) + "\n")
    
    url = df_in.iat[i,0]
    
    print(url)
    
    driver.get(url)
    data = driver.page_source
    soup = BeautifulSoup(data,'html.parser')
    
    # get listing title info
    title = soup.find("title").text.split(" | ")
    address = title[0]
    city = address.split(",")[1].replace(" ", "")
    mls = int(Decimal(sub(r'[^\d.]', '', title[1])))

    # get basic listing info
    stat_vals = soup.find_all(class_="statsValue")
    
    try:
        list_price = int(Decimal(sub(r'[^\d.]', '', stat_vals[0].text)))
    except:
        print("Login may be required to access this listing, skipping...\n")
        continue
    
    beds = stat_vals[1].text
    baths = stat_vals[2].text
    sqft = stat_vals[3].text

    # get RedFin estimate
    try:
        redfin_estimate_header = soup.find("div", class_="RedfinEstimateValueHeader").find_next("div", class_="value font-size-large")
        redfin_estimate = int(Decimal(sub(r'[^\d.]', '', redfin_estimate_header.text)))
    except:
        print("Listing does not have a RedFin estimate, using list price")
        redfin_estimate = list_price  
        
    # get home facts
    # careful when using these for calculations
    home_facts = soup.find_all("span", class_="content text-right")        
    property_type = home_facts[2].text
    num_of_units = int(Decimal(sub(r'[^\d.]', '', property_type)))
    
    # Greater than 4 units requires a commercial loan; skip these listings
    if(num_of_units > 4):
        print("Property has more than 4 units, skipping...\n")
        continue
        
    # status = home_facts[0].text
    # time_on_redfin = home_facts[1].text
    # year_built = home_facts[3].text
    # community = home_facts[4].text
    # lot_size = home_facts[5].text
    # commission = home_facts[11].text
    
    # get rental income from Zillow
    # multiply the rent by the number of units excluding the owner occupancy
    mfh_rent = getZestimate(driver, address)*(num_of_units-1)
    total_rent = mfh_rent + groveSt_rent

    # get property details 
    property_details = soup.find_all("span", class_="entryItemContent")
    for detail in property_details:
        if "Taxes:" in detail.text:
            try:
                prop_taxes = int(Decimal(sub(r'[^\d.]', '', detail.text)))/12
            except:
                print("Property taxes not available for this listing, setting taxes to zero")
                prop_taxes = 0
            break

    # multifamily mortgage calculations
    downpayment = list_price*downpayment_pct
    loan = list_price - downpayment
    closing_costs = loan*closing_costs_pct + downpayment
    insurance = (list_price*insurance_pct)/12
    pmi = (loan*pmi_pct)/12
    
    mortgage_pmt = -npf.pmt(rate/12, term*12, loan)
    mfh_piti = np.round(mortgage_pmt + prop_taxes + insurance + pmi, 2)
    
    # total monthly savings combined with 30 Grove St
    # most important metric b/c a positive value increases net worth
    total_piti = mfh_piti + groveSt_piti
    savings = np.round(groveSt_piti - (np.abs(total_rent - total_piti) + expenses), 2)
    
    # cash flows
    cash_flow_combined = np.round(total_rent - total_piti - expenses, 2)
    cash_flow_mfh = np.round(mfh_rent - mfh_piti - expenses, 2)
    cash_on_cash_rtn = np.round(((cash_flow_mfh*12) / closing_costs)*100, 1)
    
    # cap rate of MFH only
    net_operating_income = (mfh_rent - expenses)*12
    cap_rate = np.round((net_operating_income / redfin_estimate)*100, 1)
    
    print("monthly savings: $" + str(savings))
    print("MFH piti: $" + str(mfh_piti))
    # print("combined cash flow: $" + str(cash_flow_combined))
    # print("MFH cash flow: $" + str(cash_flow_mfh))
    # print("MFH CoC return: " + str(cash_on_cash_rtn) + "%")
    print("cap rate: " + str(cap_rate) + "%")
    
    if(savings > 0):
        print("Property DOES improve net worth, MLS: #" + str(mls))
        isOfInterest = True
    elif(mfh_rent == 0):
        print("Need rental information on property")
        isOfInterest = "TBD"
    else:
        print("Property DOES NOT improve net worth")
        isOfInterest = False
        
    data_out = {
        'MLS': [mls],
        'Address': [address],
        'Town/City':[city],
        'Property Type': [property_type],
        'List Price': [list_price],
        'RedFin Estimate': [redfin_estimate],
        'Beds': [beds],
        'Baths':[baths],
        'SQFT': [sqft],
        'MFH Mortgage Payment': [mfh_piti],
        'MFH Zestimate': [mfh_rent],
        'Monthly Savings': [savings],
        'MFH Cash Flow': [cash_flow_mfh],
        'MFH Cash-on-Cash Return (%)': [cash_on_cash_rtn],
        'Combined Cash Flow': [cash_flow_combined],
        'Cap Rate (%)': [cap_rate],
        'Interested?': [isOfInterest],
        'URL': [url]
    }   

    df_out = pd.DataFrame(data_out)
    df_out.to_csv(fn_out, mode='a', index=False, header=False)
    
    print("\n")

# driver.quit()

print("SCRIPT DONE!")