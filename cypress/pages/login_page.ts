export class LoginPage {
  //objects
  loginPage_SigninButton = '.nav-canvas > [ga-event="Landing page SignIn button"]'
  loginPage_MainMenu = '.nav-toggle'
  loginPage_Username = '[data-test=login-email-input]'
  loginPage_Password = '[data-test=login-password-input]'
  loginPage_LoginButton = '.login-page-new__main-form-button-text'

  /**
   * @description launch  the app
   * @param url 
   */
  navigate(url: string) {
    cy.visit(url,)
    cy.intercept(
      {
        // this RegExp matches any URL beginning with 'http://api.example.com/' and ending with '/edit' or '/save'
        url: /^http:\/\/api\.clickup\.com\//,
        headers: {
          "Authorization": "pk_10239583_XWVZ0KAU74OTU16QFM94MRRHBT1Z5RBU",
        },
      })
  }

  /**
   * @description Click on Menu
   */
  clickMenu() { cy.get(this.loginPage_MainMenu).click() }

  /**
   * @description Select Signin from Menu item
   */
  clickLoginMenu() { cy.get(this.loginPage_SigninButton).click() }

  /**
   * @description Enter User Name
   * @param username 
   */
  enterUsername(username: string) { cy.get(this.loginPage_Username).type(username) }

  /**
   * @description Enter Password
   * @param password 
   */
  enterPassword(password: string) { cy.get(this.loginPage_Password, { timeout: 6000 }).type(password) }

  /**
   * @description Click on Login button
   */
  clickLogin() { cy.get(this.loginPage_LoginButton).click() }

  validateLoginPageIsdisplayed() { cy.get(this.loginPage_LoginButton).should('exist') }

}   