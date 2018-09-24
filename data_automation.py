
import os
import pandas as pd
pd.options.mode.chained_assignment = None
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
from tabula import read_pdf
import numpy as np
import re
import PyPDF2
from docxtpl import DocxTemplate


class Data_Processor():
    """PROCESSES LUNCH AND BREAKFAST DATA"""
    
    def __init__(self, input_folder, output_folder):
        self.input_folder = input_folder
        self.output_folder = output_folder

#   FOLDER PROCESSORS

    def process_folder(self):
        self.frl_errors = []        
        self.breakfast_errors = []

        os.mkdir(self.output_folder)
        paths = [self.input_folder + "/" + fn for fn in os.listdir(self.input_folder) if fn.endswith('.pdf')]
       
        # #hacky stuff for testng
        # import random
        # paths = random.sample(paths, 15)
        for path in paths:
            print path
            self.process_pdf(path, self.output_folder)
            print "success"
        
        self.frl_errors = list(set(self.frl_errors)) 



    def process_lunch_folder(self, input_folder, output_folder, sorted_folder = ""):
        
        if sorted_folder == "":
            sorted_folder = self.output_folder

        self.counties = [fn[:-4] for fn in os.listdir(sorted_folder) if fn.endswith('.csv')]

        paths = [input_folder + "/" + fn for fn in os.listdir(input_folder) if fn.endswith('.pdf')]
        os.mkdir(output_folder)

       

        for path in paths:
            print path
            self.process_lunch(path, output_folder, sorted_folder)
            

           
            
        

#   FILE PROCESSORS


    def process_pdf(self, filename, output_folder):


        #get number of pages
        num_pages = self.countPages(filename)
        #initialize
        schools = []
        frl = []
        final = pd.DataFrame(columns = ["Breakfast YTD", "Free", "Reduced", "Paid", "ADA", "ADP", "ADP%B", "Days Served"] )

        #process all pages
        for num in range(0, num_pages):
            #get text of each page
            data = self.get_text(filename, num)
            #find county
            if num == 0:
                county = self.findCounty(data)

            #find school and frl
            school = self.findSchool(data)
            schools.extend([school])
            frl.extend([self.get_frl(school, county)])

            #get info        
            row = self.correct_row(filename, num)
            #add to final
            final = pd.concat([final, row], axis = 0)

        #add other columns   
        final["School"] = schools
        final["%FRL"] = frl

        #organize columns
        column_list = ["School","Breakfast YTD", "Free","Reduced", "Paid", "ADA", "ADP", "ADP%B", "%FRL", "Days Served"]
        final = final.reindex(columns = column_list)

        #print to csv
        name = output_folder + "/" + county + ".csv"
        final.to_csv(name)



    def process_lunch(self, filename, output_folder, sorted_folder):
        #get number of pages
        num_pages = self.countPages(filename)

        #initialize
        schools = []
        scorecard = pd.DataFrame(columns = ["Lunch Free", "Lunch Reduced", "Lunch Paid"])

        #process all pages
        for num in range(0, num_pages):
            #get text of each page
            data = self.get_text(filename, num)
           
            if num == 0:

                #find county
                county = self.findCounty(data)
            
                #find breakfast data, exit if not found
                if county in self.counties:
                    breakfast_data = self.find_breakfast(county, sorted_folder)
                else:
                    return None

                #make county folder   
                county_folder = output_folder + "/" + county
                os.mkdir(county_folder)

                #find year
                year = self.findYear(data)

            #find school
            schools.extend([self.findSchool(data)])
            #get info
            row = self.correct_row_lunch(filename,num)
            
            #add to frame
            scorecard = pd.concat([scorecard, row], axis = 0)
            
        #create frames
        final = scorecard["ADP%L"].to_frame()
        scorecard = scorecard[["Lunch Free", "Lunch Reduced", "Lunch Paid", "Days Lunch Served"]]
        
        #add schools to frames
        final["School"] = schools
        scorecard["School"] = schools  
             
        #finish frames
        final = self.finish_breakfast(final, breakfast_data)
        scorecard, average = self.finish_scorecard(scorecard, breakfast_data)
        
        # generate report card
        name = county_folder + "/" + county +" Breakfast Reportcard " + year + ".docx"
        self.generate_report_card(county, average, name, year)

        #print to csv
        name = county_folder + "/" + county + " DOE Breakfast Data " + year + ".csv"
        final.to_csv(name, index = False)

        name = county_folder + "/" + county +" Breakfast Scorecard " + year + ".csv"
        scorecard.to_csv(name, index = False)

        self.counties.remove(county)
        print "success"

 #Helper Functions

    def finish_breakfast(self, final, breakfast_data):
         
        #add data to existing breakfast data
        final = pd.merge(breakfast_data, final, on='School')

        #make numbers numeric
        final["ADP%B"] = final["ADP%B"].convert_objects(convert_numeric=True)

        #organize columns
        final["Diff"] = final["ADP%L"] - final["ADP%B"]
        
        final = final[["School","Breakfast YTD", "Free","Reduced", "Paid", "ADA", "ADP", "ADP%B","ADP%L", "%FRL", "Diff", "Days Served"]]

        return final

    def finish_scorecard(self, scorecard, breakfast_data):
        column_list = ["School", "Free", "Reduced", "Paid", "Total Breakfasts Served", "Free & Reduced-Price Breakfast Total", "Days Served", "Breakfast ADP", "Free & Reduced-Price Breakfast ADP", 
                                "Lunch Free", "Lunch Reduced", "Lunch Paid", "Total Lunches Served", "Free & Reduced-Price Lunch Total", "Days Lunch Served", "Lunch ADP", "Free & Reduced-Price Lunch ADP", "F & RP Breakfast to Lunch Ratio"]
        scorecard = pd.merge(breakfast_data, scorecard, on='School')

        #Breakfast Calculations
        
        scorecard["Free & Reduced-Price Breakfast Total"] = scorecard["Free"].convert_objects(convert_numeric=True) + scorecard["Reduced"].convert_objects(convert_numeric=True)
        scorecard["Total Breakfasts Served"] = scorecard["Free & Reduced-Price Breakfast Total"] + scorecard["Paid"]
        
        scorecard["Breakfast ADP"] = scorecard["Total Breakfasts Served"]/scorecard["Days Served"]
        scorecard["Breakfast ADP"] = scorecard["Breakfast ADP"].round()
        
        scorecard["Free & Reduced-Price Breakfast ADP"] = scorecard["Free & Reduced-Price Breakfast Total"]/scorecard["Days Served"]
        scorecard["Free & Reduced-Price Breakfast ADP"] = scorecard["Free & Reduced-Price Breakfast ADP"].round()
        
        #Lunch Calculations
        scorecard["Free & Reduced-Price Lunch Total"] = scorecard["Lunch Free"] + scorecard["Lunch Reduced"]
        scorecard["Total Lunches Served"] = scorecard["Free & Reduced-Price Lunch Total"] + scorecard["Lunch Paid"]
        
        scorecard["Lunch ADP"] = scorecard["Total Lunches Served"]/scorecard["Days Lunch Served"]
        scorecard["Lunch ADP"] = scorecard["Lunch ADP"].round()
        
        scorecard["Free & Reduced-Price Lunch ADP"] = scorecard["Free & Reduced-Price Lunch Total"]/scorecard["Days Lunch Served"]
        scorecard["Free & Reduced-Price Lunch ADP"] = scorecard["Free & Reduced-Price Lunch ADP"].round()
        
        #Ratio Calcualtions
        scorecard["F & RP Breakfast to Lunch Ratio"] = scorecard["Free & Reduced-Price Breakfast ADP"]/scorecard["Free & Reduced-Price Lunch ADP"]
        scorecard["F & RP Breakfast to Lunch Ratio"] = (scorecard["F & RP Breakfast to Lunch Ratio"]*100).round(1)
        
        #reorder
        scorecard = scorecard[column_list]

        #Ratio Average
        average = round(scorecard["F & RP Breakfast to Lunch Ratio"].mean(), 1)
        new_row = np.empty((1, len(column_list)), object)
        new_row[:,0] = "Average"
        new_row[:,-1] = average
        new_row = pd.DataFrame(new_row, columns = column_list)
        new_row.iloc[:, 1:-1] = np.nan
        scorecard = pd.concat([scorecard, new_row], ignore_index = True)
       
        return scorecard, average

    

    def get_frl(self, school, county):
        try:
            df = pd.read_csv("FRL.csv")
            df = df.loc[df["School"] == school]
            df = df.loc[df["System"] == county]
            df = df["FRL"].values[0]
            if (df == np.nan):
                raise TypeError
            else:
                return float(df)

        except:
            self.frl_errors.extend([county])
            return np.nan

    def generate_report_card(self, county, num, name, year):
        #calculate grade
        if num >= 70:
            grade = "Platinum"
        elif num >= 60:
            grade = "Gold"
        elif num >= 50:
            grade = "Silver"
        else:
            grade = "Bronze"
        
        interval = str(int(float(year)-1)) + "-" + year

        #generate document
        doc = DocxTemplate("reportcard_template.docx")
        context = { 'county' : county, "grade": grade, "year": interval}
        doc.render(context)
        doc.save(name)
            

    # find the row of table with relevant data
    def correct_row(self, filename, num):
        #use tabula to get table
        df = read_pdf(filename, pages = (num + 1))

        #get relevant row and columns
        test_df = df.loc[df.iloc[:,0] == "YTD"]
        test_df = test_df.dropna(axis = 1)
        lst = test_df.iloc[:,[6,5, 4, 1,2, 3,-2]]

        fr = lst.iloc[0,1].split()
        if len(fr) == 2:
            lst.columns = ["Breakfast YTD", "Free/Reduced", "Paid", "ADA", "ADP", "ADP%B", "Days Served"]
            #split free/reduced column
            lst["Free"] = fr[0]
            lst["Reduced"] = fr[1]
        else:
            fr = lst.iloc[0,2].split()
            if  len(fr) == 3:
                lst = lst.iloc[:,1:]
                lst.columns = ["Breakfast YTD", "Free/Reduced/Paid", "ADA", "ADP", "ADP%B", "Days Served"]
                lst["Paid"] = fr[0]
                lst["Free"] = fr[1]
                lst["Reduced"] = fr[2]
            else:

                if len(fr) == 1:
                    lst = test_df.iloc[:, [7, 5, 6, 4, 1, 2, 3,-2]]
                    lst.columns = ["Breakfast YTD", "Free", "Reduced", "Paid", "ADA", "ADP", "ADP%B", "Days Served"]
                else:
                    raise TypeError

        #order columns
        lst = lst[["Breakfast YTD", "Free", "Reduced", "Paid", "ADA", "ADP", "ADP%B", "Days Served"]]
        lst[["Breakfast YTD", "Free", "Reduced", "Paid"]] = lst[["Breakfast YTD", "Free", "Reduced", "Paid"]].applymap(lambda x: float(x.replace(',','')))
        return lst


    def correct_row_lunch(self, filename, num):
        #use tabula to get table from pdf
        df = read_pdf(filename, pages = num+1)

        #get relevant row and columns
        test_df = df.loc[df.iloc[:,0] == "YTD"]
        test_df = test_df.dropna(axis = 1)
        lst = test_df.iloc[:,[5, 4, 3,-2]]
        
        
        #split free reduced column
        fr = lst.iloc[0,0].split()
        if len(fr) == 2:
            lst.columns = ["Lunch Free/Reduced", "Lunch Paid", "ADP%L", "Days Lunch Served"]
            #split free/reduced column 
            lst["Lunch Free"] = fr[0]
            lst["Lunch Reduced"] = fr[1]
        else:
            #split free/reduced/paid column
            fr = lst.iloc[0,1].split()
            if  len(fr) == 3:
                lst = lst.iloc[:,1:]
                lst.columns = ["Free/Reduced/Paid", "ADP%L", "Days Lunch Served"]
                lst["Lunch Paid"] = fr[0]
                lst["Lunch Free"] = fr[1]
                lst["Lunch Reduced"] = fr[2]
            else:
                if len(fr) == 1:
                    lst = test_df.iloc[:,[5, 6, 4, 3,-2]]
                    lst.columns = ["Lunch Free", "Lunch Reduced", "Lunch Paid", "ADP%L", "Days Lunch Served"]
           



        #organize before returning
        lst = lst[["Lunch Free", "Lunch Reduced", "Lunch Paid", "ADP%L", "Days Lunch Served"]]
        lst = lst.applymap(lambda x: float(x.replace(',','')))
        return lst


    def find_breakfast(self, county, sorted_folder):
        name = sorted_folder + "/" + county + ".csv"
        breakfast_data = pd.read_csv(name)
        return breakfast_data


#   HELPERS

    def get_text(self, filename, num):
        
        pdfFileObj = open(filename, 'rb')
        pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
        pageObj = pdfReader.getPage(num)
        data = pageObj.extractText()
        return data

    def findYear(self, data):
        rxcounty=  "School Year : .+"
        return re.search(rxcounty,data).group()[14:]    

    def findCounty(self, data):
        rxcounty=  "System : .+"
        return re.search(rxcounty,data).group()[9:]


    def findSchool(self, data):
        rxcounty=  "School : .+"
        return re.search(rxcounty,data).group()[9:]

  
    def countPages(self, filename):
        rxcountpages = re.compile(r"/Type\s*/Page([^s]|$)", re.MULTILINE|re.DOTALL)
        data = file(filename,"rb").read()
        return len(rxcountpages.findall(data))



def removeID(string):
    return string[8:]

def cleanData(filename):
    data = pd.read_csv(filename, skiprows = 3) #uploads data
    data = data.dropna() #removes rows without data
    data = data.iloc[:,1:4] #selects columns of interest
    data.columns = ["System", "School", "FRL"] #rename columns
    data["School"] = data["School"].apply(removeID) #remove ID from school column
    data["FRL"] = data["FRL"].replace(["*", "NA", "#"], np.nan) #remove *, NA and # from frl column
    data.to_csv("FRL.csv", index = False) #write to csv
