import csv
import re
import time
import json
import os
from collections import Counter
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# File to store search history for comparison
HISTORY_FILE = "search_history.json"

def load_history():
    """Load previous search history"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history):
    """Save search history"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def setup_driver():
    """Setup and return Chrome driver in headless mode"""
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--headless')  # Enable headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080') 
    driver = webdriver.Chrome(options=options)
    return driver

def scrape_properties(driver):
    """Scrape property data from current page (FIRST PAGE ONLY)"""
    properties = []
    
    # Detect which website is showing results
    is_28hse = False
    try:
        message_element = driver.find_element(By.CSS_SELECTOR, ".ui.message")
        if "Provided By 28Hse" in message_element.text:
            is_28hse = True
            print("📌 Detected: 28Hse search results")
        else:
            print("📌 Detected: Squarefoot search results")
    except:
        try:
            gem_element = driver.find_element(By.CSS_SELECTOR, ".gem.outline.icon")
            print("📌 Detected: Squarefoot search results")
        except:
            print("📌 Detected: Standard search results")
    
    # Find all property items
    property_items = driver.find_elements(By.CSS_SELECTOR, ".property_item:not(.detail_page_others)")
    
    for prop in property_items:
        try:
            # District & Property Name
            cat_elem = prop.find_element(By.CSS_SELECTOR, ".header.cat")
            cat_text = cat_elem.text.strip()
            cat_parts = cat_text.split('\n')
            district = cat_parts[0].strip() if cat_parts else ""
            property_name = cat_parts[1].strip() if len(cat_parts) > 1 else ""
            
            # Street Address
            address = ""
            meta_elem = prop.find_elements(By.CSS_SELECTOR, ".meta")
            if meta_elem:
                address = meta_elem[0].text.strip()
            
            # Monthly Rental Price
            price = ""
            price_elem = prop.find_elements(By.CSS_SELECTOR, ".priceDesc.rentDesc")
            if price_elem:
                price_text = price_elem[0].text
                price_match = re.search(r'[\d,]+', price_text)
                price = price_match.group().replace(',', '') if price_match else ""
            
            # Area, Bedrooms, Bathrooms
            area = ""
            bedrooms = ""
            bathrooms = ""
            
            # Find the header that contains ft²
            all_headers = prop.find_elements(By.CSS_SELECTOR, ".header")
            
            for header in all_headers:
                header_text = header.text
                if 'ft²' in header_text:
                    # Extract area
                    area_match = re.search(r'([\d,]+)\s*ft²', header_text)
                    if area_match:
                        area = area_match.group(1).replace(',', '')
                    
                    # Get the inner HTML to preserve the structure
                    inner_html = header.get_attribute('innerHTML')
                    
                    # Extract bedrooms
                    bed_match = re.search(r'bed icon["\']?><\/i>\s*(\d+|studio)', inner_html, re.IGNORECASE)
                    if bed_match:
                        bedrooms = bed_match.group(1)
                        if bedrooms.lower() == 'studio':
                            bedrooms = "Studio"
                    
                    # Extract bathrooms
                    bath_match = re.search(r'bath icon["\']?><\/i>\s*(\d+)', inner_html, re.IGNORECASE)
                    if bath_match:
                        bathrooms = bath_match.group(1)
                    
                    break
            
            # Property URL
            url = ""
            if is_28hse:
                try:
                    img_element = prop.find_element(By.CSS_SELECTOR, "img.detail_page_others")
                    url = img_element.get_attribute('href')
                except:
                    try:
                        img_element = prop.find_element(By.CSS_SELECTOR, ".image.desktop_myimage img")
                        url = img_element.get_attribute('href')
                    except:
                        pass
            else:
                try:
                    img_element = prop.find_element(By.CSS_SELECTOR, "img.detail_page")
                    url = img_element.get_attribute('href')
                except:
                    try:
                        img_element = prop.find_element(By.CSS_SELECTOR, ".image.desktop_myimage img")
                        url = img_element.get_attribute('href')
                    except:
                        pass
            
            if url and '?' in url:
                url = url.split('?')[0]
            
            properties.append({
                'district': district,
                'property_name': property_name,
                'address': address,
                'price': price,
                'area': area,
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'url': url
            })
            
        except Exception as e:
            continue
    
    return properties

def save_to_csv(properties, filename):
    """Save extracted data to CSV file"""
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['District', 'Property Name', 'Street Address', 'Monthly Rent (HKD)', 
                         'Saleable Area (ft²)', 'Bedrooms', 'Bathrooms', 'Property URL']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for prop in properties:
                writer.writerow({
                    'District': prop['district'],
                    'Property Name': prop['property_name'],
                    'Street Address': prop['address'],
                    'Monthly Rent (HKD)': prop['price'],
                    'Saleable Area (ft²)': prop['area'],
                    'Bedrooms': prop['bedrooms'],
                    'Bathrooms': prop['bathrooms'],
                    'Property URL': prop['url']
                })
        
        print(f"\n✅ Data successfully saved to: {filename}")
        return True
    except Exception as e:
        print(f"\n❌ Error saving CSV file: {e}")
        return False

def display_search_results(properties):
    """Display search results count and summary"""
    if not properties:
        print("\n❌ No properties found matching your criteria!")
        return False
    
    print(f"\n{'='*60}")
    print(f" SEARCH RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"📊 Total properties found: {len(properties)}")
    
    prices = [int(p['price']) for p in properties if p['price'] and p['price'].isdigit()]
    if prices:
        print(f"💰 Price range: HKD${min(prices):,} - HKD${max(prices):,}")
        print(f"💵 Average price: HKD${sum(prices)//len(prices):,}")
    
    bedrooms = [p['bedrooms'] for p in properties if p['bedrooms']]
    if bedrooms:
        bed_counts = Counter(bedrooms)
        print(f"🛏️  Bedroom distribution: {dict(bed_counts)}")
    
    print(f"{'='*60}")
    return True

def price_analysis():
    """Perform price analysis and comparison across different searches"""
    history = load_history()
    
    if not history:
        print("\n❌ No search history found. Please perform at least one search first.")
        return
    
    print("\n" + "=" * 60)
    print(" PRICE ANALYSIS & COMPARISON")
    print("=" * 60)
    
    # Show all saved searches
    print("\n📋 Available Searches:")
    for i, search in enumerate(history, 1):
        print(f"   {i}. {search['timestamp']} - {search['district']} - {search['count']} properties - Avg: HKD${search['avg_price']:,}")
    
    # Compare all searches
    print("\n" + "-" * 40)
    print(" OVERALL STATISTICS")
    print("-" * 40)
    
    # Find best and worst deals across all searches
    all_searches = []
    for search in history:
        all_searches.append({
            'timestamp': search['timestamp'],
            'district': search['district'],
            'avg_price': search['avg_price'],
            'min_price': search['min_price'],
            'max_price': search['max_price'],
            'count': search['count']
        })
    
    if all_searches:
        # Most expensive district on average
        most_expensive = max(all_searches, key=lambda x: x['avg_price'])
        # Least expensive district on average
        least_expensive = min(all_searches, key=lambda x: x['avg_price'])
        # Most properties found
        most_properties = max(all_searches, key=lambda x: x['count'])
        # Least properties found
        least_properties = min(all_searches, key=lambda x: x['count'])
        
        print(f"\n💰 AVERAGE RENTAL PRICES BY DISTRICT:")
        for search in all_searches:
            print(f"   • {search['district']:<20} HKD${search['avg_price']:>10,} (based on {search['count']} properties)")
        
        print(f"\n🏆 MOST EXPENSIVE DISTRICT (Average):")
        print(f"   {most_expensive['district']} - HKD${most_expensive['avg_price']:,}")
        
        print(f"\n💸 LEAST EXPENSIVE DISTRICT (Average):")
        print(f"   {least_expensive['district']} - HKD${least_expensive['avg_price']:,}")
        
        print(f"\n📊 PROPERTY VOLUME:")
        print(f"   Most properties found: {most_properties['district']} ({most_properties['count']} properties)")
        print(f"   Least properties found: {least_properties['district']} ({least_properties['count']} properties)")
        
        # Price trend over time
        if len(history) >= 2:
            print(f"\n📈 PRICE TREND (Most recent vs Previous):")
            latest = history[-1]
            previous = history[-2]
            price_change = latest['avg_price'] - previous['avg_price']
            percent_change = (price_change / previous['avg_price']) * 100
            
            print(f"   {previous['timestamp'].split()[0]} → {latest['timestamp'].split()[0]}")
            print(f"   HKD${previous['avg_price']:,} → HKD${latest['avg_price']:,}")
            print(f"   Change: {'+' if price_change > 0 else ''}{price_change:,} ({percent_change:+.1f}%)")
    
    # Compare two specific searches
    if len(history) >= 2:
        print("\n" + "-" * 40)
        compare_choice = input("Do you want to compare two specific searches? (y/n): ").strip().lower()
        
        if compare_choice == 'y':
            print("\n📋 Available searches:")
            for i, search in enumerate(history, 1):
                print(f"   {i}. {search['timestamp']} - {search['district']}")
            
            try:
                first = int(input("Enter first search number: ")) - 1
                second = int(input("Enter second search number: ")) - 1
                
                if 0 <= first < len(history) and 0 <= second < len(history):
                    search1 = history[first]
                    search2 = history[second]
                    
                    print(f"\n{'='*60}")
                    print(f" COMPARISON: {search1['district']} vs {search2['district']}")
                    print(f"{'='*60}")
                    print(f"{'Metric':<25} {search1['district']:<20} {search2['district']:<20} {'Difference':<15}")
                    print(f"{'-'*80}")
                    
                    avg_diff = search1['avg_price'] - search2['avg_price']
                    print(f"{'Average Price':<25} HKD${search1['avg_price']:,<19} HKD${search2['avg_price']:,<19} {'+' if avg_diff > 0 else ''}{avg_diff:,}")
                    
                    count_diff = search1['count'] - search2['count']
                    print(f"{'Properties Found':<25} {search1['count']:<20} {search2['count']:<20} {'+' if count_diff > 0 else ''}{count_diff}")
                    
                    print(f"{'Price Range':<25} HKD${search1['min_price']:,}-{search1['max_price']:,} HKD${search2['min_price']:,}-{search2['max_price']:,}")
                else:
                    print("❌ Invalid selection!")
            except:
                print("❌ Invalid input!")
    
    print("\n" + "=" * 60)

def apply_filters(driver):
    """Apply search filters based on user input"""
    
    # Property Type Selection
    print("\n" + "-" * 40)
    print(" PROPERTY TYPE SELECTION")
    print("-" * 40)
    print("1. All")
    print("2. Apartment")
    print("3. Carpark")
    print("4. Office")
    print("5. Shop")
    
    property_types = {1: "All", 2: "Apartment", 3: "Carpark", 4: "Office", 5: "Shop"}
    
    while True:
        choice = input("\nEnter your choice (1-5): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= 5:
            type_buttons = driver.find_elements(By.CSS_SELECTOR, "div[attr='mainType'] a.item")
            type_buttons[int(choice) - 1].click()
            print(f"✅ Property type filter applied: {property_types[int(choice)]}")
            break
        else:
            print("❌ Invalid input. Please enter a number between 1 and 5.")
    
    # Budget Selection
    print("\n" + "-" * 40)
    print(" BUDGET SELECTION (HKD/month)")
    print("-" * 40)
    print("1. Any")
    print("2. Below 10,000")
    print("3. 10,000 - 20,000")
    print("4. 20,000 - 40,000")
    print("5. 40,000 - 60,000")
    print("6. 60,000 - 80,000")
    print("7. Above 80,000")
    
    budget_options = {1: "Any", 2: "Below 10,000", 3: "10,000 - 20,000", 4: "20,000 - 40,000",
                      5: "40,000 - 60,000", 6: "60,000 - 80,000", 7: "Above 80,000"}
    
    while True:
        choice = input("\nEnter your choice (1-7): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= 7:
            budget_buttons = driver.find_elements(By.CSS_SELECTOR, "div[attr='price'] a.item")
            budget_buttons = [btn for btn in budget_buttons if btn.get_attribute('data-value') != 'selfInput']
            budget_buttons[int(choice) - 1].click()
            print(f"✅ Budget filter applied: {budget_options[int(choice)]}")
            break
        else:
            print("❌ Invalid input. Please enter a number between 1 and 7.")
    
    # Area Selection
    print("\n" + "-" * 40)
    print(" AREA SELECTION (Saleable Area)")
    print("-" * 40)
    print("1. Any")
    print("2. Below 300 ft²")
    print("3. 300 ft² - 500 ft²")
    print("4. 500 ft² - 1,000 ft²")
    print("5. 1,000 ft² - 2,000 ft²")
    print("6. Above 2,000 ft²")
    
    area_options = {1: "Any", 2: "Below 300 ft²", 3: "300 ft² - 500 ft²", 
                    4: "500 ft² - 1,000 ft²", 5: "1,000 ft² - 2,000 ft²", 6: "Above 2,000 ft²"}
    
    while True:
        choice = input("\nEnter your choice (1-6): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= 6:
            area_buttons = driver.find_elements(By.CSS_SELECTOR, "div[attr='areaRange'] a.item")
            area_buttons = [btn for btn in area_buttons if btn.get_attribute('data-value') != 'selfInput']
            area_buttons[int(choice) - 1].click()
            print(f"✅ Area filter applied: {area_options[int(choice)]}")
            break
        else:
            print("❌ Invalid input. Please enter a number between 1 and 6.")
    
    # Room Selection
    print("\n" + "-" * 40)
    print(" ROOM SELECTION")
    print("-" * 40)
    print("1. Any")
    print("2. Studio")
    print("3. 1 room")
    print("4. 2 rooms")
    print("5. 3 rooms")
    print("6. 4 rooms")
    print("7. 5+ rooms")
    
    room_options = {1: "Any", 2: "Studio", 3: "1 room", 4: "2 rooms", 5: "3 rooms", 6: "4 rooms", 7: "5+ rooms"}
    
    while True:
        choice = input("\nEnter your choice (1-7): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= 7:
            room_buttons = driver.find_elements(By.CSS_SELECTOR, "div[attr='roomRange'] a.item")
            room_buttons[int(choice) - 1].click()
            print(f"✅ Room filter applied: {room_options[int(choice)]}")
            break
        else:
            print("❌ Invalid input. Please enter a number between 1 and 7.")
    
    # District Selection
    print("\n" + "-" * 40)
    print(" DISTRICT SELECTION")
    print("-" * 40)
    while True:
        district = input("Enter district name (e.g., Central, Causeway Bay, Tsim Sha Tsui): ").strip().title()
        if district:
            district_search_box = driver.find_element(By.NAME, "searchText_temp")
            district_search_box.clear()
            district_search_box.send_keys(district)
            print(f"✅ District filter applied: {district}")
            break
        else:
            print("❌ Please enter a valid district name.")

def perform_search(driver):
    """Perform a complete property search"""
    # Navigate to website
    print("\n🌐 Loading website...")
    driver.get("https://www.squarefoot.com.hk/en/rent")
    
    # Wait for page to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".property_item"))
        )
        print("✅ Website loaded successfully!")
    except:
        print("⚠️ Warning: Page may not have loaded completely...")
    
    # Apply filters
    apply_filters(driver)
    
    # Execute search
    final_search_button = driver.find_element(By.ID, "searchwords_btn")
    final_search_button.click()
    print("\n🔍 Searching for properties...")
    
    # Wait for results
    time.sleep(5)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".property_item"))
        )
        print("✅ Search completed!")
    except:
        print("⚠️ No results found or timeout...")
    
    # Scrape properties from FIRST PAGE ONLY
    print("\n📊 Extracting property data from first page...")
    properties = scrape_properties(driver)
    
    # Display search results count
    if display_search_results(properties):
        # Calculate and save statistics to history
        prices = [int(p['price']) for p in properties if p['price'] and p['price'].isdigit()]
        if prices:
            current_stats = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'district': properties[0]['district'] if properties else "Unknown",
                'count': len(properties),
                'avg_price': sum(prices) // len(prices),
                'min_price': min(prices),
                'max_price': max(prices)
            }
            history = load_history()
            history.append(current_stats)
            save_history(history)
            print(f"\n✅ Search results saved to history!")
        

        while True:
            # Ask user if they want to extract to CSV
            print("\n" + "-" * 40)
            extract_choice = input("Do you want to extract this data to a CSV file? (y/n): ").strip().lower()
            if extract_choice in ['y', 'yes']:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"property_listings_{timestamp}.csv"
                if save_to_csv(properties, filename):
                    print("\n📁 Data extraction completed successfully!")
                    break
            elif extract_choice == ['n', 'no']:
                print("\n📁 Data not extracted to CSV.")
                break
            else:
                print("❌ Invalid choice. Please Enter y/n.")
    
    return properties

def main():
    print("=" * 50)
    print(" HONG KONG RENTAL PROPERTY MARKET ANALYSER")
    print("=" * 50)
    
    driver = setup_driver()
    
    while True:
        # Main Menu
        print("\n" + "=" * 50)
        print(" MAIN MENU")
        print("=" * 50)
        print("1. Search for properties")
        print("2. Price Analysis & Comparison")
        print("3. Exit program")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "3":
            print("\n👋 Thank you for using the program. Goodbye!")
            driver.quit()
            break
        
        elif choice == "2":
            price_analysis()
            input("\nPress Enter to return to main menu...")
        
        elif choice == "1":
            perform_search(driver)
            
            # Ask if user wants to continue
            print("\n" + "-" * 40)
            while True:
                continue_choice = input("Do you want to perform another search? (y/n): ").strip().lower()
                if continue_choice in ['y', 'yes']:
                    print("\n🔄 Starting new search...\n")
                    break  # Break out of inner loop to perform another search
                elif continue_choice in ['n', 'no']:
                    print("\n👋 Thank you for using the program. Goodbye!")
                    driver.quit()
                    return  # Exit the function entirely
                else:
                    print("❌ Invalid choice. Please enter y/n.")
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()