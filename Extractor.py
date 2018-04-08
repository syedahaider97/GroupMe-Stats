import string
import urllib.request
import json
import sys
import operator
import os
import re
from datetime import datetime, timezone
from time import sleep

stream = ""
accessToken = ""

getChat = False
getCommentorStats = False
getImageLog = False
getVideoLog = False

#Setup to stage the execution of the program
def intro():
    global stream
    global accessToken
    global getChat
    global getCommentorStats
    global getImageLog
    global getVideoLog
    
    print("Hello, and welcome to the GroupMe Stats Extractor")
    print("If you do not already have an access token, please refer to the README")

    accessToken = input("Please Enter Your Access Token Now: ")
    
    print("Would you like to process a Group or a Direct Message stream?")
    while stream != 1 and stream != 2:
        stream = int(input("Enter 1 for Group, or 2 for Direct Message "))
        
    if stream == 1:
        stream = "groups"
    else:
        stream = "chats"

    allStream = []
    try:
        allStream = getAll(stream,accessToken)        
    except:
        print("\nError retrieving all " + stream + ".")
        print("Perhaps the access token was entered incorrectly.")
        print("Restarting Program...\n")
        intro()
        
    print("Which of the following " + stream + " would you like to analyze?")
    if stream == "chats":
        for  option in allStream:
            print(allStream.index(option) + 1,".\t",option["other_user"]["name"])
    elif stream == "groups":
        for option in allStream:
            print(allStream.index(option) + 1,".\t",option["name"])
   
    choice = input("Please enter your choice: ")
    while not choice.isdigit() and choice <= 0 and choice >= len(allStream):
        choice = input("Please enter a valid choice: ")
    choice = int(choice) - 1
   
    print("Which of the following would you like to enable (Please answer with 'y' or 'n'):")

    chatHistory = ""
    commentorStats = ""
    imageLog = ""
    videoLog = ""

    while len(chatHistory) < 1:
        chatHistory = input("Obtain Chat History? ")
    while len(commentorStats) < 1:
        commentorStats = input("Obtain Commentor Stats? ")
    while len(imageLog) < 1:
        imageLog = input("Obtain all Images? ")
    while len(videoLog) < 1:
        videoLog = input("Obtain all Videos? ")
    if chatHistory[0].lower() == "y":
        getChat = True
    if commentorStats[0].lower() == "y":
        getCommentorStats = True
    if imageLog[0].lower() == "y":
        getImageLog = True
    if videoLog[0].lower() == "y":
        getVideoLog = True


    if stream == "groups":
        return allStream[choice]["id"]
    elif stream == "chats":
        return allStream[choice]["other_user"]["id"]
    
#Obtains all groups/direct messages using paging
def getAll(choice, token):
    base = "https://api.groupme.com/v3"
    base += "/" + choice + "?token=" + token + "&per_page=100&omit=membership"

    jsonData = getRequest(base)
    response = jsonData["response"]

    temp = response
    k = 2
    
    while len(temp) > 0:
        link = base + "&page=" + str(k)
        temp = getRequest(link)["response"]
        response += temp
        k += 1
        link = base
        
    return response

#Returns the link used to make GET requests to construct the messagelog
def getLink(groupId):
    link = "https://api.groupme.com/v3"
    if stream == "groups":
        link += "/" + stream + "/" + groupId + "/" + "messages"
        link += "?token=" + accessToken + "&limit=100"
    elif stream == "chats":
        link += "/" + "direct_messages" + "?other_user_id=" + groupId
        link += "&token=" + accessToken + "&limit=100"
    return link

#Gets basic information about the chat. Used to obtain name and members
def getChatDetails(groupId):
    link = "https://api.groupme.com/v3"
    if stream == "groups":
        link += "/" + stream + "/" + groupId + "?token=" + accessToken
        chatInfo = getRequest(link)
        return (chatInfo["response"]["name"], chatInfo["response"]["members"])
    elif stream == "chats":
        chatInfo = getAll(stream,accessToken)
        for chat in chatInfo:
            if chat["other_user"]["id"] == groupId:
                return [chat["other_user"]["name"]]
    
    

#Leverages the URLlib to send a GET Request and maps out any forbidden characters
def getRequest(link):
    data = urllib.request.urlopen(link)
    non_bmp_map = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)
    return json.loads(data.read().decode().translate(non_bmp_map))

#Sends GET messages to build up a dictionairy(JSON) of values
#Logs the console every 500 retreieved 
def buildMessageLog(link):
    base = link
    jsonData = getRequest(link)

    total = jsonData["response"]["count"]

    messages = []    
    if stream == "groups":
        messages = jsonData["response"]["messages"]
    elif stream == "chats":
        messages = jsonData["response"]["direct_messages"]
        
    while len(messages) < total:
        try:
            lastMessage = messages[len(messages) - 1]
            lastMessageId = lastMessage["id"]
            link += "&before_id=" + lastMessageId
            
            jsonData = getRequest(link)
            
            if stream == "groups":
                messages += jsonData["response"]["messages"]
            elif stream == "chats":
                messages += jsonData["response"]["direct_messages"]
            

            link = base
            if len(messages) % 500 == 0:
                print("Obtained " + str(len(messages)) + " thus far. "
                      + str(total - len(messages)) + " remain.")
        except:
            print("Error receiving first ", str(total-len(messages)),"messages")
            break
    return messages

#Creates an html file with chat history based on the message list
#File name is the name of the chat suffixed by the date
def record(chatDetails, messageList):
    print("Beginning to Create Chat Log")
    fileName = "Record-" + chatDetails[0] + "-" + str(datetime.now())[:10] +".html"
    htmlFile = open(fileName,"w",encoding="utf-8")

    htmlFile.write("""
    <html>
    <head>
      <link rel="stylesheet" href="style.css">
    </head>
      <body>
        <table>
          <tr>
            <th> Date </th>
            <th> Sender </th>
            <th> Message </th>
          </tr>
    """)
    history = ""
    for message in messageList:
        history += """
          <tr>
            <td>""" + str(timeStandard(message["created_at"])) + """</td>
            <td>""" + str(message["name"]) + """</td>
            <td>""" + str(message["text"]) + """</td>
          </tr>
          """
    htmlFile.write(history)
    htmlFile.write("""
        </table>
      </body>
    </html>
    """)
    htmlFile.close()
    print("Succesfully Created Chat Log. Refer to", fileName, "in the Root Directory.")
    
#Obtains various stats by parsing through the message list and scanning relevant IDs
def peopleStats(chatDetails, messageList):
    print("Beginning to Obtain All User Stats")
    
    commentCount = {}
    mentionCount = {}
    likeCount = {}
    likesGiven = {}
    selfLikes = {}
    nickname = {}

    if stream == "groups":
        for member in chatDetails[1]:
            nickname[member["user_id"]] = [member["nickname"]]
    
    for message in messageList:
        senderId = message["sender_id"]
        if senderId not in commentCount:
            commentCount[senderId] = 1
        elif senderId in commentCount:
            commentCount[senderId] += 1

        for attach in message["attachments"]:
            if len(attach) > 0 and attach["type"] == "mentions":
                for user in attach["user_ids"]:
                    if user not in mentionCount:
                        mentionCount[user] = 1
                    elif user in mentionCount:
                        mentionCount[user] += 1
                    
        if senderId not in likeCount:
            likeCount[senderId] = len(message["favorited_by"])
        elif senderId in likeCount:
            likeCount[senderId] += len(message["favorited_by"])

        for user in message["favorited_by"]:
            if user not in likesGiven:
                likesGiven[user] = 1
            elif user in likesGiven:
                likesGiven[user] += 1

            if senderId == user:
                if user not in selfLikes:
                    selfLikes[user] = 1
                elif user in selfLikes:
                    selfLikes[user] += 1
                    
        if senderId not in nickname:
            nickname[senderId] = []
        if message["name"] not in nickname[senderId]:
            nickname[senderId].append(message["name"])
    
    print("\n~~~~~~~~~~~~~~~~~TOTAL COMMENTS~~~~~~~~~~~~~~~\n")
    commentRanking = displayStats(nickname,commentCount)
    print("Total Comments: ", sum(commentRanking.values()))

    print("\n~~~~~~~~~~~~~~~~~TOTAL MENTIONS~~~~~~~~~~~~~~~\n")
    mentionRanking = displayStats(nickname,mentionCount)
    print("Total Mentions: ", sum(mentionRanking.values()))

    print("\n~~~~~~~~~~~~~~TOTAL LIKES RECEIVED~~~~~~~~~~~~\n")
    likeRanking = displayStats(nickname,likeCount)
    print("Total Likes: ", sum(likeRanking.values()))

    print("\n~~~~~~~~~~~~~~~TOTAL LIKES GIVEN~~~~~~~~~~~~~~\n")
    givenRanking = displayStats(nickname,likesGiven)
    print("Total Likes Given: ", sum(likesGiven.values()))

    print("\n~~~~~~~~~~~~~~~~TOTAL SELF LIKES~~~~~~~~~~~~~~\n")
    selfRanking = displayStats(nickname,selfLikes)
    print("Total Self Likes Given: ", sum(selfRanking.values()))
    
    print("\nFinished Displaying All User Stats")
    

#Obtains the images from users and avatar changes and renames them based on
#uploader and date
def obtainImages(messageList):
    print("Beginning to Obtain All Images")
    translator=str.maketrans('','',string.punctuation)
    for message in messageList:
        try:
            attachment = message["attachments"]
            if len(attachment) > 0:
                for attach in attachment:
                    if attach["type"] == "image":
                        picName = message["name"] + " "
                        picName = picName.translate(translator)
                        picName += timeStandard(message["created_at"]) + ".jpeg"
                        urllib.request.urlretrieve(attach["url"],picName)
            elif message["sender_id"] == "system":
                if "event" in message and len(message["event"]) > 0:
                    event = message["event"]
                    if event["type"] == "group.avatar_change":
                        picName = "Avatar Change " + event["data"]["user"]["nickname"] + " "
                        picName += timeStandard(message["created_at"])+ ".jpeg"
                        urllib.request.urlretrieve(event["data"]["avatar_url"],picName)
        except:
            errorMessage = "Error getting picture by " + message["name"]
            errorMessage += " at time " + timeStandard(message["created_at"])
            print(errorMessage)
    print("Obtaining Images Complete")

#Obtains all videos from chat and renames them based on uploader and date
def obtainVideos(messageList):
    print("Beginning to Obtain All Videos")
    regex = r"(https://v.groupme.com/.*\.mp4)"
    
    translator=str.maketrans('','',string.punctuation)
    
    
    for message in messageList:
        try:
            text = message["text"]
            if text and re.search(regex,text):
                vidName = message["name"] + " "
                vidName = vidName.translate(translator)
                vidName += timeStandard(message["created_at"]) + ".mp4"
                urllib.request.urlretrieve(re.search(regex,text).group(0),vidName)
        except:
            errorMessage = "Error getting video by " + message["name"]
            errorMessage += " at time " + timeStandard(message["created_at"])
            print(errorMessage)

            
    print("Obtaining Videos Complete")
        
        
            
        

##################Utility Functions######################

#Takes a dictionairy {userId:[nicknames]} and sorts them in desending order
def displayStats(nickname,statsDict):
    ranking = {}
    
    for user in statsDict:
        try:
            if len(nickname[user]) > 1 and len(nickname[user]) < 5:
                ranking[tuple(nickname[user])] = statsDict[user]
            else:
                ranking[nickname[user][0]] = statsDict[user]
        except:
            print("Error Logging User:", user)
        
    sortedRanking = sorted(ranking.items(),key = operator.itemgetter(1))

    for entry in sortedRanking[::-1]:
        print(entry)
        
    return ranking

#Used to convert time to a human readable value 
def timeStandard(epochTime):
    utcTime = datetime.fromtimestamp(epochTime, timezone.utc)
    
    return utcTime.astimezone().strftime("%m-%d-%Y %H-%M-%S")

def main():
    groupId = intro()
    link = getLink(groupId)
    print()
    allMessages = buildMessageLog(link)
    chatDetails = getChatDetails(groupId)
    print()
    if getChat:
        record(chatDetails, allMessages[::-1])
        print()
    if getCommentorStats:
        peopleStats(chatDetails, allMessages[::-1])
        print()
    if getImageLog:
        obtainImages(allMessages)
        print()
    if getVideoLog:
        obtainVideos(allMessages)
        print()
    print("Thank you for using GroupMe Stats!")
    
if __name__ == "__main__":
    main()
