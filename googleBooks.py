#!/usr/bin/env python3

import sys
import os
import requests
import json
import time
import xmltodict
import re

import googleBooksEnv

outfile = googleBooksEnv.path
googleKey = googleBooksEnv.key
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


jsonOut = []

def getBooks():
    count = 0
    books = []
    almaUrl = f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/analytics/reports?path=%2Fshared%2FNortheastern%20University%2FJohnShared%2FAPI%2FNewBooksWeb&limit=25&apikey={almaKey}"
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
            book['mmsId'] = mmsId
            
            isbns = row['Column3']
            match = re.match(r'.*(978\d{10})', isbns)
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
                    books.append(book)
                    count = count + 1
                else:
                    print("Thumbnail too small")
            except:
                print(f"ERROR getting Cover URL: {book['coverurl']}")
    else:
        sys.exit("FAILED TO GET ALALYTICS DATA")
        
    return books, count
    
jsonOut, count = getBooks()

print(f"Writing {count} books to {outfile}")
        
with open(outfile, "w") as j:
    json.dump(jsonOut, j, indent=4)

print('DONE')
