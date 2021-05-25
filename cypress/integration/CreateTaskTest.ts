///<reference types = "cypress"/>

import { LoginPage } from "../pages/login_page"
import { HomePage } from "../pages/home_page"
let loginPage = new LoginPage()
let homepage = new HomePage()
describe('clickup New item - Test', function (){
   
    it('Clickup Login - Test', function () {
        loginPage.navigate(Cypress.env('url'))
        loginPage.clickMenu()
        loginPage.clickLoginMenu()
        loginPage.enterUsername(Cypress.env('usernameAdmin'))
        loginPage.enterPassword(Cypress.env('passwordAdmin'))
        loginPage.clickLogin()
        homepage.validateSideBar()
    })
    it('Clickup NewTask - Test', function () {
        homepage.clickNewTaskbutton()
        homepage.validateNewTaskPageIsDisplayed();
        homepage.enterTaskName("Task123")
        homepage.selectTheCategoryItem(Cypress.env('listName'))
        homepage.enterTaskDescription("This is a new Task")
        homepage.clickSelectUserAssignment("Me")
        homepage.clickCreateTask();    
    })

    it('Clickup Logout- Test', function () {
        homepage.clickLogout();
        loginPage.validateLoginPageIsdisplayed()
    }) 
    
    /* it('Clickup Update the New Task in List', function () {})
    it('Clickup Validate the Updated Task in List ', function () {})
     */
})