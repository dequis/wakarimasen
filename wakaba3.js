function get_cookie(name)
{
	with(document.cookie)
	{
		var regexp=new RegExp("(^|;\\s+)"+name+"=(.*?)(;|$)");
		var hit=regexp.exec(document.cookie);
		if(hit&&hit.length>2) return unescape(hit[2]);
		else return '';
	}
};

function passfield(num,adminmode) // Bring up Password Field for [Edit] and [Delete] Links
{
	if (lastopenfield != num || document.getElementById("movethreadselect")) // If the field isn't present...
	{
		// Collapse other fields
		if (lastopenfield) { collapse_field(lastopenfield); }

		// Clear form.
		document.getElementById("delform").reset();
		
		// Assemble new field
		var label = document.createElement("label");
		var bracket_left = document.createTextNode("[");
		var checkbox = document.createElement("input");
		checkbox.setAttribute("type","checkbox");
		checkbox.setAttribute("name","postfileonly");
		checkbox.setAttribute("value","on");
		var label_text = document.createTextNode(" File Only?] ");
		label.appendChild(bracket_left);
		label.appendChild(checkbox);
		label.appendChild(label_text);

		if (!adminmode)
		{
			var field = document.createElement("input");
			field.setAttribute("type","password");
			field.setAttribute("id","password"+num);
			field.setAttribute("name","postpassword");
			field.setAttribute("size","8");
			field.setAttribute("value", get_password("password"));
		}
		
		var spacer = document.createTextNode(" ");
		
		var submit = document.createElement("input");
		submit.setAttribute("type","submit");
		submit.setAttribute("value","OK");
		submit.setAttribute("name","singledelete");
		
		var hiddenInfo = document.createElement("input");
		hiddenInfo.setAttribute("type","hidden");
		hiddenInfo.setAttribute("name","deletepost");
		hiddenInfo.setAttribute("value",num);
		
		var hiddenTask = document.createElement("input");
		hiddenTask.setAttribute("type","hidden");
		hiddenTask.setAttribute("name","task");
		hiddenTask.setAttribute("value","Delete");
		
		var selectedspan = document.getElementById('delpostcontent'+num);
		selectedspan.appendChild(label);
		if (!adminmode)
			selectedspan.appendChild(field);
		selectedspan.appendChild(spacer);
		selectedspan.appendChild(submit);
		selectedspan.appendChild(hiddenInfo);	
		selectedspan.appendChild(hiddenTask);	
		
		// This is now the current open delete field
		lastopenfield = num;
	}
	else
	{
		collapse_field(num);
		// No fields open now
		lastopenfield = 0;
	}
}

function move_thread_field(num)
{
	if (lastopenfield != num || !document.getElementById("movethreadselect"))
	{
		var boards = new Array();
		var board;

		// Collapse other fields
		if (lastopenfield) { collapse_field(lastopenfield); }
		
		// Clear form.
		document.getElementById("delform").reset();

		var boardSelect = document.getElementById("boardselect").getElementsByTagName("select")[0];
		if (boardSelect.firstChild)
		{
			boards.push(boardSelect.firstChild.getAttribute("value"));
			board = boardSelect.firstChild;

			while (board.nextSibling)
			{
				board = board.nextSibling;
				boards.push(board.getAttribute("value"));
			}
		}

		var newBoardSelect = document.createElement("select");
		newBoardSelect.setAttribute("name","destboard");

		while (boards.length > 0)
		{
			var boardName = boards.shift();
			var newOption = document.createElement("option");
			newOption.setAttribute("id","movethreadselect");
			newOption.setAttribute("value",boardName);
			var optionText = document.createTextNode(boardName);
			newOption.appendChild(optionText);
			newBoardSelect.appendChild(newOption);
		}

		var submit = document.createElement("input");
		submit.setAttribute("type","submit");
		submit.setAttribute("value","OK");
		
		var hiddenInput = document.createElement("input");
		hiddenInput.setAttribute("type","hidden");
		hiddenInput.setAttribute("name","num");
		hiddenInput.setAttribute("value",num);

		var hiddenTask = document.createElement("input");
		hiddenTask.setAttribute("type","hidden");
		hiddenTask.setAttribute("name","task");
		hiddenTask.setAttribute("value","move");
		
		var selectedspan = document.getElementById('movethreadcontent'+num);
		selectedspan.appendChild(newBoardSelect);
		selectedspan.appendChild(submit);
		selectedspan.appendChild(hiddenInput);	
		selectedspan.appendChild(hiddenTask);	
		
		// This is now the current open delete field
		lastopenfield = num;
	}
	else
	{
		collapse_field(num);
		// No fields open now
		lastopenfield = 0;
	}
}

function collapse_field(num)
{
	var newspan = document.createElement("span");

	if (!document.getElementById("movethreadselect"))
	{
		var form = document.getElementById("deletelink"+num);
		var selectedspan = document.getElementById('delpostcontent'+num);
		form.replaceChild(newspan,selectedspan);
		newspan.style.display = "inline";
		selectedspan.setAttribute("id","");
		newspan.setAttribute("id","delpostcontent"+num);
	}
	else
	{
		var form = document.getElementById("movelink"+num);
		var selectedspan = document.getElementById('movethreadcontent'+num);
		form.replaceChild(newspan,selectedspan);
		newspan.style.display = "inline";
		selectedspan.setAttribute("id","");
		newspan.setAttribute("id","movethreadcontent"+num);
	}
}

function set_cookie(name,value,days)
{
	if(days)
	{
		var date=new Date();
		date.setTime(date.getTime()+(days*24*60*60*1000));
		var expires="; expires="+date.toGMTString();
	}
	else expires="";
	document.cookie=name+"="+value+expires+"; path=/";
}

function get_password(name)
{
	var pass=get_cookie(name);
	if(pass) return pass;

	var chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
	var pass='';

	for(var i=0;i<8;i++)
	{
		var rnd=Math.floor(Math.random()*chars.length);
		pass+=chars.substring(rnd,rnd+1);
	}

	return(pass);
}



function insert(text)
{
	var textarea=document.forms.postform.comment;
	text = text + "\n";
	if(textarea)
	{
		if(textarea.createTextRange && textarea.caretPos) // IE
		{
			var caretPos=textarea.caretPos;
			caretPos.text=caretPos.text.charAt(caretPos.text.length-1)==" "?text+" ":text;
		}
		else if(textarea.setSelectionRange) // Firefox
		{
			var start=textarea.selectionStart;
			var end=textarea.selectionEnd;
			textarea.value=textarea.value.substr(0,start)+text+textarea.value.substr(end);
			textarea.setSelectionRange(start+text.length,start+text.length);
		}
		else
		{
			textarea.value+=text+" ";
		}
		//textarea.focus();
	}
}

function highlight(post)
{
	var cells=document.getElementsByTagName("td");
	for(var i=0;i<cells.length;i++) if(cells[i].className=="highlight") cells[i].className="reply";

	var reply=document.getElementById("reply"+post);
	if(reply)
	{
		reply.className="highlight";
/*		var match=/^([^#]*)/.exec(document.location.toString());
		document.location=match[1]+"#"+post;*/
		return false;
	}

	return true;
}



function set_stylesheet(styletitle,norefresh)
{
	set_cookie("wakabastyle",styletitle,365);

	var links=document.getElementsByTagName("link");
	var found=false;
	for(var i=0;i<links.length;i++)
	{
		var rel=links[i].getAttribute("rel");
		var title=links[i].getAttribute("title");
		if(rel.indexOf("style")!=-1&&title)
		{
			links[i].disabled=true; // IE needs this to work. IE needs to die.
			if(styletitle==title) { links[i].disabled=false; found=true; }
		}
	}
	if(!found) set_preferred_stylesheet();
}

function set_preferred_stylesheet()
{
	var links=document.getElementsByTagName("link");
	for(var i=0;i<links.length;i++)
	{
		var rel=links[i].getAttribute("rel");
		var title=links[i].getAttribute("title");
		if(rel.indexOf("style")!=-1&&title) links[i].disabled=(rel.indexOf("alt")!=-1);
	}
}

function get_active_stylesheet()
{
	var links=document.getElementsByTagName("link");
	for(var i=0;i<links.length;i++)
	{
		var rel=links[i].getAttribute("rel");
		var title=links[i].getAttribute("title");
		if(rel.indexOf("style")!=-1&&title&&!links[i].disabled) return title;
	}
	return null;
}

function get_preferred_stylesheet()
{
	var links=document.getElementsByTagName("link");
	for(var i=0;i<links.length;i++)
	{
		var rel=links[i].getAttribute("rel");
		var title=links[i].getAttribute("title");
		if(rel.indexOf("style")!=-1&&rel.indexOf("alt")==-1&&title) return title;
	}
	return null;
}

function set_inputs(id,adminMode) { with(document.getElementById(id)) {if(!field1.value) field1.value=get_cookie("name"); if(!email.value) email.value=get_cookie("email"); subject.value=""; if(!adminMode) { if (!password.value) password.value=get_password("password"); } } } 
function set_delpass(id) { with(document.getElementById(id)) {password.value=get_cookie("password"); } }


function do_ban(el)
{
	var reason=prompt("Give a reason for this ban:");
	if(reason) document.location=el.href+"&comment="+encodeURIComponent(reason);
	return false;
}

window.onunload=function(e)
{
	if(style_cookie)
	{
		var title=get_active_stylesheet();
		set_cookie(style_cookie,title,365);
	}
}

window.onload=function(e)
{
	var match;

	if(match=/#i([0-9]+)/.exec(document.location.toString()))
	if(!document.forms.postform.comment.value)
	insert(">>"+match[1]);

	if(match=/#([0-9]+)/.exec(document.location.toString()))
	highlight(match[1]);
}

if(style_cookie)
{
	var cookie=get_cookie(style_cookie);
	var title=cookie?cookie:get_preferred_stylesheet();
	set_stylesheet(title);
}

function threadHide(id)
{
	toggleHidden(id);
	add_to_thread_cookie(id);
}

function threadShow(id)
{
	document.getElementById(id).style.display = "";
	
	var threadInfo = id + "_info";
	var parentform = document.getElementById("delform");
	var obsoleteinfo = document.getElementById(threadInfo);
	obsoleteinfo.setAttribute("id","");
	var clearedinfo = document.createElement("div");
	clearedinfo.style.cssFloat = "left";
	clearedinfo.style.styleFloat = "left"; // Gee, thanks, IE.
	parentform.replaceChild(clearedinfo,obsoleteinfo);
	clearedinfo.setAttribute("id",threadInfo);
	
	var hideThreadSpan = document.createElement("span");
	var hideThreadLink = document.createElement("a");
	hideThreadLink.setAttribute("href","javascript:threadHide('"+id+"')");
	var hideThreadLinkText = document.createTextNode("Hide Thread (\u2212)");
	hideThreadLink.appendChild(hideThreadLinkText);
	hideThreadSpan.appendChild(hideThreadLink);
	
	var oldSpan = document.getElementById(id+"_display");
	oldSpan.setAttribute("id","");
	parentform.replaceChild(hideThreadSpan,oldSpan);
	hideThreadLink.setAttribute("id","toggle"+id);
	hideThreadSpan.setAttribute("id",id+"_display");
	hideThreadSpan.style.cssFloat = "right";
	hideThreadSpan.style.styleFloat = "right";
	
	remove_from_thread_cookie(id);
}

function add_to_thread_cookie(id)
{
	var hiddenThreadArray = get_cookie(thread_cookie);
	if (hiddenThreadArray.indexOf(id + ",") != -1)
	{			
		return;
	}
	else
	{
		set_cookie(thread_cookie, hiddenThreadArray + id + ",", 365);
	}
}

function remove_from_thread_cookie(id)
{
	var hiddenThreadArray = get_cookie(thread_cookie);
	var myregexp = new RegExp(id + ",", 'g');
	hiddenThreadArray = hiddenThreadArray.replace(myregexp, "");
	set_cookie(thread_cookie, hiddenThreadArray, 365);
}

function toggleHidden(id)
{
	var id_split = id.split("");
	if (id_split[0] == "t")
	{
		id_split.reverse();
		var shortenedLength = id_split.length - 1;
		id_split.length = shortenedLength;
		id_split.reverse();
	}
	else
	{
		id = "t" + id; // Compatibility with an earlier mod
	}
	if (document.getElementById(id))
	{
		document.getElementById(id).style.display = "none";
	}
	var thread_name = id_split.join("");
	var threadInfo = id + "_info";
	if (document.getElementById(threadInfo))
	{
		var hiddenNotice = document.createElement("em");
		var hiddenNoticeText = document.createTextNode("Thread " + thread_name + " hidden.");
		hiddenNotice.appendChild(hiddenNoticeText);
		
		var hiddenNoticeDivision = document.getElementById(threadInfo);
		hiddenNoticeDivision.appendChild(hiddenNotice);
	}
	var showThreadText = id + "_display";
	if (document.getElementById(showThreadText)) 
	{
		var showThreadSpan = document.createElement("span");
		var showThreadLink = document.createElement("a");
		showThreadLink.setAttribute("href","javascript:threadShow('"+id+"')");
		var showThreadLinkText = document.createTextNode("Show Thread (+)");
		showThreadLink.appendChild(showThreadLinkText);
		showThreadSpan.appendChild(showThreadLink);
		
		var parentform = document.getElementById("delform");
		var oldSpan = document.getElementById(id+"_display");
		oldSpan.setAttribute("id","");
		parentform.replaceChild(showThreadSpan,oldSpan);
		showThreadLink.setAttribute("id","toggle"+id);
		showThreadSpan.setAttribute("id",id+"_display");
		showThreadSpan.style.cssFloat = "right";
		showThreadSpan.style.styleFloat = "right";
	}
}

function popUp(URL) {
	day = new Date();
	id = day.getTime();
	eval("page" + id + " = window.open(URL, '" + id + "', 'toolbar=0,scrollbars=1,location=0,statusbar=0,menubar=0,resizable=1,width=450,height=300');");
}
function popUpPost(URL) 
{
	day = new Date();
	id = day.getTime();
	eval("page" + id + " = window.open(URL, '" + id + "', 'toolbar=0,scrollbars=1,location=0,statusbar=0,menubar=0,resizable=1,width=600,height=350');");
}
