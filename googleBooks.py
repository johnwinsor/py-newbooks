#!/usr/bin/env python3

import sys
import os
import requests
import json
import time
import xmltodict
import re

import googleBooksEnv

records = sys.argv[1]
# outfile = sys.argv[2]

outfile = googleBooksEnv.path
googleKey = googleBooksEnv.googleKey
almaKey = googleBooksEnv.almaKey
print(f"Writing data to {outfile}")

def checkOpenLibImage(isbn):
    openLibMetadataUrl = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json"
    response = requests.get(openLibMetadataUrl)
    if response.status_code == 200:
        data = response.json()
        key = f"ISBN:{isbn}"
        if key in data:
            return data[key]
        else:
            return None
    else:
        return None
    
def titlecase(s):
    return re.sub(
        r"[A-Za-z]+('[A-Za-z]+)?",
        lambda word: word.group(0).capitalize(),
        s)

def getSummary(isbn):
    googleUrl = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&key={googleKey}"
    response = requests.get(googleUrl)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        return None

def getGoogleBigCover(url):
    zoomed = re.sub("zoom=5", "zoom=10", url)
    uncurled = re.sub("&edge=curl", "", zoomed)
    https = re.sub("http:", "https:", uncurled)
    return https
        
def getGoogleCover(googleBook):
    if 'imageLinks' in googleBook['items'][0]['volumeInfo']:
        smallThumbnail = googleBook['items'][0]['volumeInfo']['imageLinks']['smallThumbnail']
        googleSmallThumbnail = re.sub("http:", "https:", smallThumbnail)
        googleSmallThumbnailResponse = requests.get(googleSmallThumbnail, allow_redirects=True)
        googleSmallThumbnailImageSize = googleSmallThumbnailResponse.headers.get("Content-Length")
        print(f"googleSmallThumbnailImageSize - {googleSmallThumbnailImageSize}")
        
        googleBigCover = getGoogleBigCover(googleSmallThumbnail)
        googleBigCoverResponse = requests.get(googleBigCover, allow_redirects=True)
        googleBigCoverImageSize = googleBigCoverResponse.headers.get("Content-Length")
        print(f"googleBigCoverImageSize - {googleBigCoverImageSize}")
        if int(googleBigCoverImageSize) > 150000:
            print("LARGE GOOGLE PLACEHOLDER IMAGE Found - Falling back to small thumbnail")
            return googleSmallThumbnail
        elif int(googleBigCoverImageSize) == 9103:
            print("IMAGE NOT AVAILABLE GOOGLE PLACEHOLDER IMAGE Found - Falling back to small thumbnail")
            return googleSmallThumbnail
        elif int(googleBigCoverImageSize) < int(googleSmallThumbnailImageSize):
            print("Small Thumbnail larger than Big Cover - Falling back to Small Thumbnail")
            return googleSmallThumbnail
        else:
            print("Using Zoomed Google Cover")
            return googleBigCover
    else:
        return None

def getBooks():
    print("Opening current data file...")
    
    with open(outfile) as json_file:
        jsonData = json.load(json_file)
        dataLength = len(jsonData)
        print(f"Found {dataLength} existing records")
        
        newCount = 0
        existingCount = 0
        # books = []
        almaUrl = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/analytics/reports?path=%2Fshared%2FNortheastern%20University%2FJohnShared%2FAPI%2FNewBooksWeb&limit={records}&apikey={almaKey}"
        print(almaUrl)
        response = requests.get(almaUrl)
        if response.status_code == 200:
            my_dict = xmltodict.parse(response.content)
            rows = my_dict['report']['QueryResult']['ResultXml']['rowset']['Row']
            for row in rows:
                time.sleep(1)
                print("---------------------------")
                book = {}
                
                mmsId = row['Column4']
                if any(dictionary.get('mmsId') == mmsId for dictionary in jsonData):
                    print("ALREADY IN DATA")
                    existingCount += 1
                    continue
                else:
                    print("NOT IN DATA")
                
                book['mmsId'] = mmsId
                
                isbns = row['Column3']
                match = re.match(r'.*(9\d{12})', isbns)
                isbn = match.groups()[0]
                print(isbn)
                book['isbn'] = isbn
                
                title = row['Column7']
                title = titlecase(title)
                title = re.sub("\/", "", title)
                print(title)
                book['title'] = title
                
                if 'Column1' in row:
                    author = row['Column1']
                    author = titlecase(author)
                else:
                    author = ""
                book['author'] = author
                
                recStatus = row['Column19']
                book['recStatus'] = recStatus
                
                recDate = row['Column16']
                book['recDate'] = recDate
                
                callNo = row['Column10']
                print(f"Call Number: {callNo}")
                book['callNo'] = callNo
                
                location = row['Column13']
                print(f"Location: {location}")
                book['location'] = location
                
                subject = row['Column21']
                book['subject'] = subject
                
                googleBook = getSummary(isbn)

                try:
                    if 'description' in googleBook['items'][0]['volumeInfo']:
                        summary = googleBook['items'][0]['volumeInfo']['description']
                        book['summary'] = summary
                    else:
                        book['summary'] = "No summary."
                except:
                    print("Error encountered parsing Google Metadata")
                    print(json.dumps(googleBook, indent=4))
                    continue
                
                hasOpenLibrary = checkOpenLibImage(isbn)
                
                if hasOpenLibrary:
                    if 'thumbnail_url' in hasOpenLibrary:
                        coverurl = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
                        print(f"Using OpenLibrary Cover: {coverurl}")
                        book['coverurl'] = coverurl
                    else:
                        print("NO OPEN LIBRARY COVER - Checking Google Books...")
                        googleCover = getGoogleCover(googleBook)
                        if googleCover is None:
                            print(f"No Google cover - Skipping title")
                            continue
                        else:
                            print(f"Using Google Cover: {googleCover}")
                            book['coverurl'] = googleCover
                else:
                    print("NO OPEN LIBRARY METADATA - Checking Google Books...")
                    googleCover = getGoogleCover(googleBook)
                    if googleCover is None:
                        print(f"No Google cover - Skipping title")
                        continue
                    else:
                        print(f"Using Google Cover: {googleCover}")
                        book['coverurl'] = googleCover
                
                print(f"Checking image site for cover: {book['coverurl']}")
                try:
                    coverurlResponse = requests.get(book['coverurl'], allow_redirects=True)

                    if coverurlResponse.history:
                        final_redirect = coverurlResponse.history[-1]
                        final_headers = final_redirect.headers
                        imageURL = final_headers["location"]
                        imageURLResponse = requests.get(imageURL, stream=True)
                        raw_content = imageURLResponse.raw.read()
                        image_size = len(raw_content)
                        print(f"IMAGE-SIZE(OL): {image_size}")
                        
                    else:
                        image_size = coverurlResponse.headers.get("Content-Length")
                        print(f"IMAGE-SIZE(Google): {image_size}")
                        if image_size is None:
                            imageURLResponse = requests.get(imageURL, stream=True)
                            raw_content = imageURLResponse.raw.read()
                            image_size = len(raw_content)
                            print(f"IMAGE-SIZE(none): {image_size}")
                    
                    if int(image_size) > 15000:    
                        print("Adding book to data file...")
                        jsonData.append(book)
                        newCount = newCount + 1
                    else:
                        print("Thumbnail too small")
                except:
                    print(f"ERROR getting Cover URL: {book['coverurl']}")
        else:
            sys.exit("FAILED TO GET ALALYTICS DATA")
            
        return jsonData, newCount, existingCount
    
jsonOut, count, existingCount = getBooks()

print(f"Appending {count} new book(s) to exising {existingCount} books in {outfile}.")
        
with open(outfile, "w") as j:
    json.dump(jsonOut, j, indent=4)

print('DONE')
