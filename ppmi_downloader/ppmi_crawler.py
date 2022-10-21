from ppmi_navigator import PPMINavigator


class PPMICrawler(PPMINavigator):
    '''
    A class to crawl PPMI website    
    '''
    
    def __init__(self, driver) -> None:
        super().__init__(driver)
        
    def crawl_Download_StudyData(self):
        self.html.login()
        
    
    