import {Component, EventEmitter, Input, OnChanges, Output} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {JsonSchema} from '../../../models/workflow';
import {validateInput} from './workflow-format';
import {WorkflowInputFieldComponent} from './workflow-input-field.component';

@Component({
  selector:'app-workflow-input-editor', standalone:true,
  imports:[FormsModule,MatButtonModule,WorkflowInputFieldComponent],
  templateUrl: './workflow-input-editor.component.html',
  styleUrl: './workflow-input-editor.component.scss',
})
export class WorkflowInputEditorComponent implements OnChanges {
  @Input() schema:JsonSchema={}; @Input() text='{}'; @Output() textChange=new EventEmitter<string>();
  value:Record<string,unknown>={}; advanced=false; error='';
  get properties(){return Object.entries(this.schema.properties??{});}
  ngOnChanges(){if(!this.parse())this.advanced=true;}
  setField(name:string,value:unknown){this.value={...this.value,[name]:value};if(value===undefined)delete this.value[name];this.text=JSON.stringify(this.value,null,2);this.error='';this.textChange.emit(this.text);}
  setText(text:string){this.text=text;this.parse();this.textChange.emit(text);}
  toggle(){if(this.advanced&&!this.parse())return;this.advanced=!this.advanced;}
  validate(){if(!this.parse())return false;this.error=validateInput(this.value,this.schema)??'';return !this.error;}
  private parse(){try{const parsed=JSON.parse(this.text||'{}');if(!parsed||Array.isArray(parsed)||typeof parsed!=='object')throw new Error();this.value=parsed;this.error='';return true;}catch{this.error='Workflow input must be a valid JSON object.';return false;}}
}
