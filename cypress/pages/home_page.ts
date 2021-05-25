
export class HomePage {
    //objects  
    homePage_SideBar = '.cu-simple-bar__container'
    homePage_NewTask = '.cu-float-button__toggle-simple-container-create-task'
    homePage_SelectCategorydropdown = '.cu-draft-location-selector__selection-text_truncate'
    homePage_SearchCategoryInput = '.cu2-hierarchy-picker__search-input'
    homePage_NewTaskSelectCategoryItem = '.cu2-hierarchy-picker__items'
    homePage_NewTaskDescription = '.notranslate > .ql-editor'
    homePage_ProfileMenu = '.cu-avatar-container > .cu-avatar'
    homePage_Logout = '[data-test=user-settings-menu-item-log-out]'
    homePage_TaskAsigneedropdown = '.cu-user-group__icon > svg'
    homePage_Userlist = 'user-list'
    homePage_CreateTask = '[data-test=draft-view__submit-btn_createTask]'
    homePage_NewTaskTitle = '.cdk-textarea-autosize'
    homePage_UserListItem = '.user-list-item__name'
    homePage_TaskName = 'textarea'
    /**
     * @description launch a 
     * @param url 
     */
    validateSideBar() { cy.get(this.homePage_SideBar).should('exist') }

    /**
     * 
     */
    clickNewTaskbutton() { cy.get(this.homePage_NewTask).click() }

    /**
     * 
     */
    selectCategory() { cy.get(this.homePage_SelectCategorydropdown).click() }

    /**
     * 
     * @param categoryName 
     */
    enterCategorySearch(categoryName: string) { cy.get(this.homePage_SearchCategoryInput).type(categoryName) }

    /**
     * 
     * @param categoryName 
     */
    selectTheCategoryItem(categoryName: string) {
        this.selectCategory()
        this.enterCategorySearch(categoryName)
        cy.get(this.homePage_NewTaskSelectCategoryItem).contains(categoryName).click()
    }

    /**
    * 
    * @param description 
    */
    enterTaskName(taskName: string) {

    
        cy.get(this.homePage_TaskName).type(taskName)
    }

    /**
     * 
     * @param description 
     */
    enterTaskDescription(description: string) { cy.get(this.homePage_NewTaskDescription).type(description + new Date()) }

    /**
     * 
     */
    clickAsignee() { cy.get(this.homePage_TaskAsigneedropdown).click() }

    /**
     * 
     * @param asignee 
     */
    clickSelectUserAssignment(asignee: string) {
        this.clickAsignee();
        cy.get(this.homePage_UserListItem)
            .contains('Me').click()
    }

    /**
     * 
     */
    clickavatar() { cy.get(this.homePage_ProfileMenu).click() }

    /**
     * 
     */
    clickLogout() {
        this.clickavatar()
        cy.get(this.homePage_Logout).click()
    }

    /**
     * 
     */
    clickCreateTask() { cy.get(this.homePage_CreateTask).click() }

    /**
     * 
     */
    validateNewTaskPageIsDisplayed() { cy.get(this.homePage_NewTaskTitle).should('exist') }
}   