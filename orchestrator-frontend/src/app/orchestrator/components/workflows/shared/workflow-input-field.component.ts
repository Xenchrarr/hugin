import {Component, EventEmitter, Input, Output} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatCheckboxModule} from '@angular/material/checkbox';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {JsonSchema} from '../../../models/workflow';
import {exampleInput, formatWorkflowKey, validateInput} from './workflow-format';

@Component({
  selector: 'app-workflow-input-field', standalone: true,
  imports: [FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule],
  templateUrl: './workflow-input-field.component.html',
  styleUrl: './workflow-input-field.component.scss',
})
export class WorkflowInputFieldComponent {
  @Input() name=''; @Input() schema:JsonSchema={}; @Input() value:unknown; @Input() required=false;
  @Output() valueChange=new EventEmitter<unknown>(); error='';
  get label(){return this.schema.title || formatWorkflowKey(this.name);} get type(){return Array.isArray(this.schema.type)?this.schema.type[0]:this.schema.type;}
  get properties(){return Object.entries(this.schema.properties??{});} get objectValue(){return this.value && typeof this.value==='object'&&!Array.isArray(this.value)?this.value as Record<string,unknown>:{};}
  get arrayValue(){return Array.isArray(this.value)?this.value:[];}
  change(value:unknown){this.value=value;this.error=validateInput(value,this.schema,this.label)??'';this.valueChange.emit(value);}
  numberChanged(event:Event){const input=event.target as HTMLInputElement;this.change(input.value===''?undefined:input.valueAsNumber);}
  initialize(){this.change(exampleInput({type:'object',properties:{value:this.schema},required:['value']})['value']);}
  setProperty(name:string,value:unknown){const next={...this.objectValue,[name]:value};if(value===undefined)delete next[name];this.change(next);}
  setItem(index:number,value:unknown){const next=[...this.arrayValue];next[index]=value;this.change(next);}
  addItem(){this.change([...this.arrayValue,exampleInput({type:'object',properties:{value:this.schema.items??{}},required:['value']})['value']]);}
  removeItem(index:number){this.change(this.arrayValue.filter((_,i)=>i!==index));}
}
