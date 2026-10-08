const { configureProjects, unsharded } = require("./reporting/projects");
const {defineConfig}=require('@playwright/test');
const inherited=unsharded(require('./playwright.config'));
const projects=inherited.projects.map(project=>({...project,metadata:{required_case_count:4}}));
module.exports=configureProjects(defineConfig({...inherited,testMatch:'**/diagrams.spec.js',projects,
 reporter:inherited.reporter.map(entry=>Array.isArray(entry)&&String(entry[0]).endsWith('strict-reporter.js')?[entry[0],{...entry[1],scope:'single_owner_diagrams',requiredProjects:projects.map(p=>p.name)}]:entry)}));
