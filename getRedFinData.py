# -*- coding: utf-8 -*-
"""
Created on Fri Mar 18 20:20:19 2022

Determines whether a RedFin listing  will cash flow. Note that login 
credentials may be required to access certain data such as rent estimates.
Google Chrome cookies must be enabled to remain logged in. This cookie data is 
passed in with chrome_options.

# TODO: find ways to speed this script up
# https://seleniumjava.com/2015/12/12/how-to-make-selenium-webdriver-scripts-faster/

@author: jcartagena
"""

from IPython import get_ipython
get_ipython().magic('clear')

# constants
term = 30 # years
# TODO: get rate from McGlone website
rate = 0.0475 # FHA: 4.75%, Conv: 5% as of 4/23/22
pmi_pct = 0.0085 # 0.85% of loan amount [McGlone history]
insurance_pct = 0.004 # 0.4% of list price
downpayment_pct = 0.035 # FHA: 3.5%, Conventional: 5% (owner occupied)
closing_costs_pct = 0.01 # 1% is typical for McGlone
expenses = 536.96 # monthly (utilities, reserves, maintenance, etc)

groveSt_rent = 3200 # current home's rental potential
groveSt_piti = 2598.28 # current mortgage pmt

import time
# import requests
import datetime
from re import sub
import numpy as np
import pandas as pd
from tkinter import Tk
from decimal import Decimal
import numpy_financial as npf
from bs4 import BeautifulSoup
from selenium import webdriver
from fake_useragent import UserAgent
from tkinter.filedialog import askopenfilename

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
        zestimate = 0

    return zestimate

# get timestamp
ct = str(datetime.datetime.now().strftime("%m-%d-%Y_%H%M%S"))

# use random user agents to try and bypass walls such as CAPTCHA
userAgent = UserAgent().random

chrome_options = webdriver.ChromeOptions()

chrome_options.headless = False
# chrome_options.add_argument('--window-size=1920,1080')
# chrome_options.add_argument(f'user-agent={userAgent}')
chrome_options.add_argument("--proxy-server='direct://'")
chrome_options.add_argument("--proxy-bypass-list=*")
# chrome_options.add_argument("blink-settings=imagesEnabled=false")
chrome_options.add_argument("user-data-dir=C:\\Users\\jabie\\AppData\\Local\\Google\\Chrome\\User Data")
chrome_options.add_experimental_option("prefs", {"download.default_directory" : "C:\\Users\\jabie\\Documents\\Finance\\Real Estate Investing\\code\\input"})

driver = webdriver.Chrome("chromedriver", options=chrome_options)

# this is the saved "Automated MA House Hack" search url
# areas: middlesex, suffolk, and norfolk counties
# price range: 0-$1M, beds: 4+, baths: 2+, type: multifamily
# status: "active", "coming soon", no HOA fees, no new construction
# exclude 55+ communities, short sales, and land leases
# sort by newest listings first
# remove 'viewport'
search_url = "https://www.redfin.com/county/1344/MA/Norfolk-County/filter/" +\
             "sort=lo-days,property-type=multifamily,max-price=1.00M,min-beds=4,"+\
             "min-baths=2,hoa=0,exclude-short-sale,exclude-age-restricted,"+\
             "exclude-land-lease,mr=5:1346+5:1342"

driver.get(search_url)

time.sleep(3)

search_data = driver.page_source
search_soup = BeautifulSoup(search_data,'html.parser')

download_url = "https://www.redfin.com" + str(search_soup.find("a", id="download-and-save")["href"])

# # without this header, RedFin will require a CAPTCHA during automation
# headers = {
#     'User-Agent' : userAgent,
#     'Cookie': 'RF_BID_UPDATED=1; RF_BROWSER_ID=_jrORlGfQJyzST1Hn6CAOQ; RF_MARKET=boston'
# }

# # request the data dump from RedFin
# response = requests.get(download_url, headers=headers).content

# # # save data to a CSV file
# with open("input/redfin_data.csv", 'wb') as outfile:
#     outfile.write(response)

# download the RedFin csv file
driver.get(download_url)

# show the "select file" dialog box
Tk().withdraw() 
filepath = askopenfilename() 

# read in RedFin URLs
# df_in = pd.read_csv("test.csv", usecols=[20])
df_in = pd.read_csv(filepath, usecols=[20])

# read in average MA rents by towns/cities
avg_mass_rent = pd.read_csv("mass_avg_rent.csv")
cities = list(avg_mass_rent.iloc[:,0].values)

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
    'Unit Info':[],
    'RedFin Rent Estimate per Unit':[],
    'MA Average Rent per Unit': [],
    'Zillow Rent Estimate':[],
    'Rent Estimate Used': [],
    'MFH Mortgage Payment': [],
    'Monthly Savings': [],
    'MFH Cash Flow': [],
    'MFH Cash-on-Cash Return (%)': [],
    'Combined Cash Flow': [],
    'Cap Rate (%)': [],
    'Interested?': [],
    'URL': [],
    'Notes':[]
}  

df_out = pd.DataFrame(data_out)
df_param = pd.DataFrame(params)

fn_out = "output/data/output_" + ct + ".csv"
fn_param = "output/params/parameters_" + ct + ".csv"

df_out.to_csv(fn_out, mode='a', index=False, header=True)
df_param.to_csv(fn_param, mode='a', index=False, header=True)

notes = []
rf_rents = []
avg_rents = []
unit_info = []

for i in range(0, len(df_in)):
    
    print(str(i+1) + " of " + str(len(df_in)) + "\n")
        
    url = df_in.iat[i,0]
    
    print(url)
    
    driver.get(url)
    data = driver.page_source
    soup = BeautifulSoup(data,'html.parser')

    # clear list contents
    notes.clear()
    rf_rents.clear()
    avg_rents.clear()
    unit_info.clear()

    # get listing title info
    title = soup.find("title").text.split(" | ")
    address = title[0]
    city = address.split(",")[1].replace(" ", "")
    mls = str(Decimal(sub(r'[^\d.]', '', title[1])))
    
    # locate city index to get average rent info
    try:
        if(city != ""):
            city_idx = int(cities.index(city))
    except:
        print("City: " + city + " is not in average MA rent list")

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
        notes.append("Listing does not have a RedFin estimate, using list price")
        redfin_estimate = list_price  
        
    # get home facts
    # careful when using these for calculations as listing indicies can change
    # TODO: there's probably a nicer way of doing this
    home_facts = soup.find_all("span", class_="content text-right")   
    property_type = home_facts[0].text
    # print(property_type)
    try:
        num_of_units = int(Decimal(sub(r'[^\d.]', '', property_type)))
    except:
        notes.append("exception: " + property_type)
    
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
      
    # get unit information
    for i in range(num_of_units):
        
        unit_beds = "0"
        unit_baths = "0"
        unit_rent = 0
        avg_rent = 0
        
        s = "Unit #" + str(i+1) + " Information"
        
        try:
            unit_info_header = soup.find(string=s).find_parents("ul")
            unit_info_list = str(unit_info_header).split("<li class=\"entryItem\"><span class=\"entryItemContent\">")
        except:
            notes.append("No individual unit info available")
            continue
            
        for item in unit_info_list:
            if("# of Bedrooms: " in item):
                unit_beds = int(Decimal(sub(r'[^\d.]', '', item)))
                
                # no data available for greater than 4 bedrooms
                if(unit_beds > 4):
                    notes.append("no MA rent data on greater than 4 bedrooms")
                else:
                    if(city != ""):
                        avg_rent = int(avg_mass_rent.iloc[city_idx][str(unit_beds) + "BR"])
                    else:
                        notes.append("city not found in average MA rent list")
                
            if("# of Full Baths: " in item):               
                unit_baths = str(Decimal(sub(r'[^\d.]', '', item)))
                            
            if("Rent: " in item):
                unit_rent = int(Decimal(sub(r'[^\d.]', '', item)))
                # unit_rent_fmt = "${:,d}".format(unit_rent)
        
        rf_rents.append(unit_rent)
        avg_rents.append(avg_rent)
        unit_info.append({"beds": str(unit_beds), "baths": unit_baths})

    # get zestimate
    zillow_rent = getZestimate(driver, address) 
    # zillow_rent = getZestimate(driver, address)*(num_of_units-1) 

    # determine which rent estimate to use
    if(np.sum(rf_rents) == 0):
        if(zillow_rent == 0):
            mfh_rent = 0
            notes.append("Property does not have a zestimate, set rent to zero")  
        else:
            mfh_rent = zillow_rent  
            notes.append("Used zestimate in calculations")
    else:
        # sort the RedFin rents and only take the top (num_of_units - 1) rents
        # one unit's rent is reserved for the owner and is not accounted for
        mfh_rent = np.sum((np.sort(rf_rents)[::-1])[0:num_of_units-1])
    
    total_rent = mfh_rent + groveSt_rent
 
    # get property taxes 
    try:
        taxes_header = str(soup.find(string="Taxes: ").find_parents("span"))
        prop_taxes = int(Decimal(sub(r'[^\d.]', '', taxes_header)))/12
    except:
        notes.append("Property taxes not available for this listing, setting taxes to zero")
        prop_taxes = 0

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
    savings = np.round(total_rent - total_piti + groveSt_piti - expenses, 2)
    
    # cash flows
    cash_flow_combined = np.round(total_rent - total_piti - expenses, 2)
    cash_flow_mfh = np.round(mfh_rent - mfh_piti - expenses, 2)
    cash_on_cash_rtn = np.round(((cash_flow_mfh*12) / closing_costs)*100, 1)
    
    # cap rate of MFH only
    net_operating_income = (mfh_rent - expenses)*12
    cap_rate = np.round((net_operating_income / redfin_estimate)*100, 1)
    
    # determine if property has a good cap rate (8-12%)
    if(8 <= cap_rate <= 12):
        notes.append("Property has a good cap rate")
    
    print(unit_info)
    print("redfin rents: " + str(rf_rents))
    # print("monthly savings: $" + str(savings))
    print("MFH piti: $" + str(mfh_piti))
    # print("combined cash flow: $" + str(cash_flow_combined))
    print("MFH cash flow: $" + str(cash_flow_mfh))
    print("MFH CoC return: " + str(cash_on_cash_rtn) + "%")
    print("cap rate: " + str(cap_rate) + "%")
    
    if(mfh_rent == 0):
        isOfInterest = "See notes"
    if(savings > 0):
        print("Property DOES improve net worth, MLS: #" + mls)
        isOfInterest = True
    else:
        # print("Property DOES NOT improve net worth")
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
        'Unit Info':[unit_info],
        'RedFin Rent Estimate per Unit':[rf_rents],
        'MA Average Rent per Unit': [avg_rents],
        'Zillow Rent Estimate':[zillow_rent],
        'Rent Estimate Used': [mfh_rent],
        'MFH Mortgage Payment': [mfh_piti],
        'Monthly Savings': [savings],
        'MFH Cash Flow': [cash_flow_mfh],
        'MFH Cash-on-Cash Return (%)': [cash_on_cash_rtn],
        'Combined Cash Flow': [cash_flow_combined],
        'Cap Rate (%)': [cap_rate],
        'Interested?': [isOfInterest],
        'URL': [url],
        'Notes': [notes]
    }   

    df_out = pd.DataFrame(data_out)
    df_out.to_csv(fn_out, mode='a', index=False, header=False)
    
    print("\n")

driver.quit()

print("SCRIPT DONE!")